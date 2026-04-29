import logging
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(pre_save, sender='tournaments.Tournament')
def _store_previous_status(sender, instance, **kwargs):
    """Zapamiętaj poprzedni status przed zapisem (potrzebne w post_save)."""
    if instance.pk:
        try:
            instance._previous_status = sender.objects.values_list('status', flat=True).get(pk=instance.pk)
        except sender.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


@receiver(post_save, sender='tournaments.Tournament')
def rebuild_rankings_on_tournament_finish(sender, instance, created, **kwargs):
    """
    Odbuduj precomputed rankings gdy turniej zmienia status na FIN.

    Zabezpieczenia:
    - Odpala się tylko przy zmianie → FIN (nie ponownie gdy już był FIN).
    - Nie odpala przy tworzeniu nowego turnieju (created=True).
    - Wymaga ustawionego end_date (bez daty nie ma sezonu do rebuild).
    - Loguje co i kiedy zostało odbudowane.
    """
    if created:
        return

    previous = getattr(instance, '_previous_status', None)
    current = instance.status

    # Trigger tylko przy przejściu → FIN, nie gdy już był FIN
    if current != 'FIN' or previous == 'FIN':
        return

    if not instance.end_date:
        logger.warning(
            '[rankings] Turniej id=%d zmienił status na FIN, ale brak end_date — pomijam rebuild.',
            instance.pk,
        )
        return

    season = instance.end_date.year
    match_type = instance.match_format

    logger.info(
        '[rankings] Turniej "%s" (id=%d) → FIN. Rebuild rankingów: match_type=%s, season=%d.',
        instance.name, instance.pk, match_type, season,
    )

    try:
        from apps.rankings.services import ranking_calculator
        count = ranking_calculator.rebuild_rankings(match_type=match_type, season=season)
        logger.info(
            '[rankings] Rebuild zakończony: %d wpisów zaktualizowanych (match_type=%s, season=%d).',
            count, match_type, season,
        )
    except Exception as exc:
        logger.error(
            '[rankings] Błąd rebuild rankingów dla turnieju id=%d: %s',
            instance.pk, exc, exc_info=True,
        )
