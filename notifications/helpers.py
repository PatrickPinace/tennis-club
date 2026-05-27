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


def notify(user: User, message: str) -> None:
    """
    Tworzy notyfikację dla podanego użytkownika.

    - Nie rzuca wyjątku — awaria notyfikacji nie blokuje głównej akcji.
    - Nie wysyła do anonimów (brak user.pk lub is_authenticated=False).
    - Ogranicza message do 255 znaków (limit modelu).
    """
    if not user or not getattr(user, 'pk', None):
        return
    try:
        from notifications.models import Notifications
        Notifications.objects.create(
            user=user,
            message=message[:255],
        )
    except Exception:
        logger.exception('notify(): failed to create notification for user_id=%s', getattr(user, 'pk', '?'))
