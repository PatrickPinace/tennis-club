# notifications/helpers.py
#
# Lekki helper do tworzenia notyfikacji produktowych z poziomu API views.
# Importuj jako:
#   from notifications.helpers import notify
#
# Nie importuje nic z apps.* — zero ryzyka circular import.

import logging
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


def notify(
    user: User,
    message: str,
    target_url: str | None = None,
    event_type: str | None = None,
) -> None:
    """
    Tworzy in-app notyfikację dla podanego użytkownika.

    - Nie rzuca wyjątku — awaria notyfikacji nie blokuje głównej akcji.
    - Nie wysyła do anonimów (brak user.pk).
    - message: max 255 znaków; target_url: max 500 znaków.
    - event_type: opcjonalny identyfikator zdarzenia (np. 'court.reservation.created').
      Jeśli nie podany, zapisuje 'generic'. Używany w przyszłości do preferencji i
      filtrowania per kanał.
    """
    if not user or not getattr(user, 'pk', None):
        return
    try:
        from django.utils import timezone
        from notifications.models import Notifications
        Notifications.objects.create(
            user=user,
            message=message[:255],
            target_url=target_url[:500] if target_url else None,
            event_type=event_type or 'generic',
            channel='inapp',
            delivery_status='delivered',
            sent_at=timezone.now(),
        )
    except Exception:
        logger.exception('notify(): failed to create notification for user_id=%s', getattr(user, 'pk', '?'))
