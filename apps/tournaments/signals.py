from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='tournaments.Tournament')
def rebuild_rankings_on_tournament_finish(sender, instance, **kwargs):
    """Rebuild precomputed rankings when a tournament is marked as finished."""
    if instance.status == 'FIN':
        from apps.rankings.services.ranking_calculator import rebuild_rankings
        rebuild_rankings(
            match_type=instance.match_format,
            season=instance.end_date.year if instance.end_date else None,
        )
