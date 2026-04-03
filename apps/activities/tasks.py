import logging
from django.contrib.auth import get_user_model
from django_q.tasks import async_task
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

# Importuj funkcję synchronizującą z widoków
from .views import _sync_user_activities

logger = logging.getLogger(__name__)
User = get_user_model()


def sync_single_user_garmin_data(user_id):
    """
    Zadanie wykonywane przez workera dla pojedynczego użytkownika.
    Loguje się do Garmin i uruchamia synchronizację aktywności.
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.error(f"Sync task failed: User with ID {user_id} does not exist.")
        return

    profile = getattr(user, 'profile', None)
    if not profile or not profile.garmin_login or not profile.garmin_password:
        logger.warning(f"Sync task skipped: User {user.username} has no Garmin credentials.")
        return

    logger.info(f"Rozpoczynanie synchronizacji w tle dla użytkownika: {user.username}")
    try:
        # Logowanie do Garmin Connect
        client = Garmin(profile.garmin_login, profile.garmin_password)
        client.login()
        # Wywołanie istniejącej logiki synchronizacji
        saved, failed = _sync_user_activities(user, client)
        logger.info(f"Zakończono zadanie tła dla {user.username}. Zapisano: {saved}, Błędy {failed}")

    except GarminConnectAuthenticationError:
        logger.error(f"Błąd autentykacji Garmin w zadaniu w tle dla użytkownika {user.username}. Sprawdź hasło.")
    except (GarminConnectConnectionError, GarminConnectTooManyRequestsError) as e:
        logger.error(f"Błąd połączenia z Garmin dla {user.username} w zadaniu w tle: {e}")
    except Exception as e:
        logger.error(f"Nieoczekiwany błąd podczas synchronizacji w tle dla {user.username}: {e}")


def sync_all_users_garmin_data():
    """
    Pobiera wszystkich użytkowników, którzy mają zapisane poświadczenia Garmin
    i zleca dla każdego z nich OSOBNE asynchroniczne zadanie synchronizacji.
    """
    users_with_credentials = User.objects.filter(
        profile__garmin_login__isnull=False,
        profile__garmin_password__isnull=False
    ).exclude(profile__garmin_login='').exclude(profile__garmin_password='')

    logger.info(f"Znaleziono {users_with_credentials.count()} użytkowników do synchronizacji. Zlecanie zadań...")

    for user in users_with_credentials:
        # Zlecamy zadanie asynchronicznie. Dzięki temu awaria jednego nie blokuje reszty,
        # a zadania mogą się wykonywać równolegle (zależnie od liczby workerów).
        async_task('apps.activities.tasks.sync_single_user_garmin_data', user.id)
        
    logger.info("Zlecono wszystkie zadania synchronizacji użytkowników.")