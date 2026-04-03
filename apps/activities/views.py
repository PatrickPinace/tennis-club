from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import logging
from garminconnect import (
    Garmin,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
    GarminConnectAuthenticationError,
)
import datetime
from .models import Activity, TennisData
from django.contrib.contenttypes.models import ContentType
from apps.tournaments.models import TournamentsMatch
from django_q.models import Schedule, Success
from apps.matches.models import Match
from django.utils import timezone
from django.db.models import Q
from django.utils.dateparse import parse_datetime
from fitparse import FitFile, FitParseError
from io import BytesIO
import os
import zipfile
import json

# Zastępujemy problematyczny import. Używamy prostszego sprawdzenia typu wiadomości.
# W nowszych wersjach fitparse FitDataMessage jest często importowany z core.
# W tej wersji kodu polegamy na checku 'if record.name == "session":'
try:
    from fitparse.exc import FitHeaderError
except ImportError:
    FitHeaderError = FitParseError

logger = logging.getLogger(__name__)


def parse_tennis_data(fit_file_bytes):
    """
    Parsuje plik FIT w poszukiwaniu danych deweloperskich z aplikacji Tennis Studio.
    Używa stabilnej metody iteracji po polach wiadomości 'session', omijając 
    niestabilną metodę get_developer_fields().
    """
    # Mapowanie nazw pól z FIT (klucze w małych literach) na nazwy pól w modelu TennisData (wartości)
    FIELD_MAP = {
        'score': 'score',
        'points': 'points',
        'serving points': 'serving_points',
        'aces': 'aces',
        'double faults': 'double_faults', 
        'first serve %': 'first_serve_percentage', 
        'win % on first serve': 'win_percentage_on_first_serve', 
        'win % on second serve': 'win_percentage_on_second_serve', 
        'receiving points': 'receiving_points',
        'games': 'games',
        'breakpoints': 'breakpoints',
        'set points': 'set_points',
        'match points': 'match_points',
        'sets durations': 'sets_durations',
        'winners': 'winners',
        'unforced errors': 'unforced_errors',
    }
    parsed_data = {}

    try:
        if not fit_file_bytes:
            logger.warning("Otrzymano puste dane pliku FIT. Nie można parsować.")
            return parsed_data

        fitfile = FitFile(BytesIO(fit_file_bytes), check_crc=False)

        # Przechodzimy przez wszystkie wiadomości w poszukiwaniu podsumowania sesji
        for record in fitfile.get_messages():

            # Sprawdzamy, czy to wiadomość 'session'
            if hasattr(record, 'name') and record.name == 'session':

                # --- KLUCZOWA ZMIANA: Bezpośrednia iteracja po wszystkich polach (record.fields) ---
                for field in record.fields:

                    if field.name:
                        # Używamy małych liter dla spójności
                        field_name_lower = field.name.lower()
                    else:
                        continue

                        # Weryfikacja, czy nazwa pola pasuje do naszych statystyk tenisowych
                    if field_name_lower in FIELD_MAP:
                        model_field_name = FIELD_MAP[field_name_lower]
                        value = field.value

                        if value is not None:                            
                            # Jeśli pole to 'sets_durations' i wartość jest listą, łączymy ją w tekst
                            if model_field_name == 'sets_durations' and isinstance(value, list):
                                parsed_data[model_field_name] = " ".join(map(str, value))
                            # W przeciwnym razie, po prostu konwertujemy wartość na string.
                            # Jest to bezpieczne, ponieważ wszystkie pola w modelu TennisData są typu CharField.
                            else:
                                parsed_data[model_field_name] = str(value)

                # Przetworzyliśmy wszystkie pola w wiadomości 'session', przerywamy pętlę
                break

    except (FitParseError, FitHeaderError) as e:
        logger.error(
            f"Błąd parsowania pliku FIT ({type(e).__name__}): {e}. Plik mógł być uszkodzony lub nieprawidłowy.")
    except Exception as e:
        logger.error(f"Nieoczekiwany błąd podczas parsowania pliku FIT: {e}. Typ błędu: {type(e).__name__}")

    return parsed_data


def _process_fit_data(client, activity, activity_id):
    """
    Pobiera, przetwarza plik FIT dla danej aktywności i zapisuje dane tenisowe.
    Zwraca True w przypadku sukcesu, False w przypadku błędu.
    """
    try:
        fit_data = client.download_activity(activity_id, dl_fmt=client.ActivityDownloadFormat.ORIGINAL)

        if not fit_data:
            logger.warning(f"Pobrane dane dla aktywności {activity_id} są puste.")
            return False

        # Sprawdzenie, czy odpowiedź nie jest stroną błędu (np. HTML)
        if fit_data.strip().startswith(b'<'):
            logger.error(f"Pobrane dane dla aktywności {activity_id} wyglądają na HTML. Plik nie zostanie przetworzony.")
            return False

        # Obsługa archiwum ZIP
        if fit_data.startswith(b'PK\x03\x04'):
            logger.info(f"Pobrane dane dla aktywności {activity_id} to archiwum ZIP. Próba rozpakowania.")
            try:
                with zipfile.ZipFile(BytesIO(fit_data)) as z:
                    fit_filename = next((name for name in z.namelist() if name.lower().endswith('.fit')), None)
                    if fit_filename:
                        fit_data = z.read(fit_filename)
                    else:
                        logger.error(f"Nie znaleziono pliku .fit w archiwum ZIP dla aktywności {activity_id}.")
                        return False
            except zipfile.BadZipFile:
                logger.error(f"Błąd podczas rozpakowywania archiwum ZIP dla aktywności {activity_id}.")
                return False

        if tennis_dev_data := parse_tennis_data(fit_data):
            TennisData.objects.update_or_create(activity=activity, defaults=tennis_dev_data)
            activity.tennis_data_fetched = True
            activity.save(update_fields=['tennis_data_fetched'])
            logger.info(f"Zapisano/zaktualizowano dane deweloperskie dla aktywności {activity_id}.")
            return True
        else:
            logger.info(f"Nie znaleziono danych deweloperskich Tennis Studio w pliku FIT dla aktywności {activity_id}.")
            return False

    except Exception as e:
        logger.error(f"Nie udało się pobrać lub przetworzyć pliku FIT dla aktywności {activity_id}. Błąd: {e}")
        return False

def _sync_user_activities(user, client):
    """
    Logika synchronizacji aktywności Garmin dla danego użytkownika.
    Pobiera 30 ostatnich aktywności i zapisuje te, których brakuje w bazie danych.
    """
    logger.info(f"Rozpoczęcie synchronizacji dla użytkownika {user.username}")
    saved_activities_count = 0
    failed_activities_count = 0

    # Sprawdź, czy to pierwsza synchronizacja dla tego użytkownika
    is_first_sync = not Activity.objects.filter(user=user).exists()

    activities_to_process = []
    existing_activities_map = {}

    try:
        if is_first_sync:
            logger.info(f"Pierwsza synchronizacja dla użytkownika {user.username}. Pobieranie wszystkich aktywności tenisowych.")
            start = 0
            limit = 50  # Pobieramy w paczkach po 50
            while True:
                activities_batch = client.get_activities(start, limit)
                if not activities_batch:
                    break  # Koniec aktywności

                # Filtrujemy aktywności zgodnie z wyborem użytkownika
                if user.profile.garmin_sync_option == 'TENNIS_ONLY':
                    activities_to_add = [
                        act for act in activities_batch 
                        if act.get("activityType", {}).get("typeKey") == "tennis_v2"
                    ]
                else: # 'ALL'
                    activities_to_add = activities_batch
                activities_to_process.extend(activities_to_add)
                logger.info(f"Pobrano {len(activities_batch)} aktywności, dodano {len(activities_to_add)}. Łącznie do przetworzenia: {len(activities_to_process)}")
                start += limit
        else:
            logger.info(f"Kolejna synchronizacja dla użytkownika {user.username}. Sprawdzanie ostatnich 30 aktywności.")
            # Pobierz 30 ostatnich aktywności
            activities_to_process = client.get_activities(0, 30)
            if not activities_to_process:
                logger.info(f"Nie znaleziono żadnych nowych aktywności Garmin dla {user.username}.")
                return 0, 0

            logger.info(f"Znaleziono {len(activities_to_process)} aktywności do potencjalnej synchronizacji dla {user.username}.")
            
            # Pobieramy mapę {activity_id: tennis_data_fetched} dla istniejących aktywności
            existing_activities_map = {
                act.activity_id: act.tennis_data_fetched for act in Activity.objects.filter(user=user)
            }

    except Exception as e:
        logger.error(f"Wystąpił błąd podczas pobierania listy aktywności Garmin dla {user.username}: {e}")
        return 0, 0

    if not activities_to_process:
        if is_first_sync:
            logger.info(f"Nie znaleziono żadnych aktywności tenisowych dla {user.username} podczas pierwszej synchronizacji.")
        else:
            logger.info(f"Brak nowych aktywności do zsynchronizowania dla {user.username}.")
        return 0, 0

    logger.info(f"Rozpoczynanie przetwarzania {len(activities_to_process)} aktywności dla {user.username}.")

    try:
        for activity_data in activities_to_process:
            activity_id = activity_data.get("activityId")

            # --- DEBUG: Zapisz konkretną aktywność do pliku ---
            # if activity_id == 14832121083:
            #     try:
            #         with open(f'activity_{activity_id}_data.json', 'w', encoding='utf-8') as f:
            #             json.dump(activity_data, f, ensure_ascii=False, indent=4)
            #         logger.info(f"ZAPISANO DANE DEBUG: Aktywność {activity_id} została zapisana do pliku activity_{activity_id}_data.json")
            #     except Exception as e:
            #         logger.error(f"BŁĄD ZAPISU DANYCH DEBUG: Nie udało się zapisać aktywności {activity_id} do pliku. Błąd: {e}")
            # --- KONIEC DEBUG ---

            is_tennis_activity = activity_data.get("activityType", {}).get("typeKey") == "tennis_v2"
            activity_exists = activity_id in existing_activities_map
            tennis_data_is_fetched = existing_activities_map.get(activity_id, False)

            # Pomiń, jeśli aktywność istnieje i (nie jest tenisowa LUB dane tenisowe są już pobrane)
            if activity_exists and (not is_tennis_activity or tennis_data_is_fetched):
                continue


            try:
                if not activity_id:
                    logger.warning(f"Pominięto aktywność bez ID dla użytkownika {user.username}: {activity_data}")
                    failed_activities_count += 1
                    continue

                start_time_str = activity_data.get("startTimeLocal")
                if not start_time_str:
                    logger.warning(f"Pominięto aktywność {activity_id} z powodu braku czasu rozpoczęcia.")
                    failed_activities_count += 1
                    continue

                start_time = parse_datetime(start_time_str)
                if not start_time:
                    logger.warning(f"Nie można sparsować start_time_str: '{start_time_str}' dla aktywności {activity_id}")
                    failed_activities_count += 1
                    continue

                activity_defaults = {
                    'user': user,
                    'activity_name': activity_data.get("activityName", "N/A"),
                    'activity_type_key': activity_data.get("activityType", {}).get("typeKey"),
                    'start_time': start_time,
                    'duration': activity_data.get("duration", 0),
                    'distance': activity_data.get("distance", 0),
                    'average_hr': activity_data.get("averageHR"),
                    'max_hr': activity_data.get("maxHR"),
                    'calories': activity_data.get("calories"),
                }

                activity, created = Activity.objects.update_or_create(
                    activity_id=activity_id,
                    defaults=activity_defaults
                )
                if created:
                    saved_activities_count += 1
                    logger.info(f"Zapisano nową aktywność {activity_id} dla {user.username}.")
                else:
                    # To nie powinno się zdarzyć z powodu wcześniejszego sprawdzenia, ale dla bezpieczeństwa
                    logger.info(f"Zaktualizowano istniejącą aktywność {activity_id} dla {user.username}.")

                # Jeśli to aktywność tenisowa, spróbuj pobrać dane z pliku FIT
                if is_tennis_activity:
                    logger.info(f"Aktywność tenisowa {activity_id}. Próba pobrania danych z pliku FIT.")
                    if not _process_fit_data(client, activity, activity_id):
                        # Jeśli pobieranie danych się nie powiedzie, oznaczamy jako błąd, ale kontynuujemy
                        failed_activities_count += 1

            except Exception as e:
                failed_activities_count += 1
                logger.error(f"Nie udało się zapisać aktywności {activity_data.get('activityId')} dla {user.username}. Błąd: {e}")
                # W przypadku błędu zapisu aktywności, przechodzimy do następnej

    except Exception as e: # Ten blok łapie błędy z pętli przetwarzającej
        logger.error(f"Wystąpił nieoczekiwany błąd podczas przetwarzania aktywności dla {user.username}: {e}")
    logger.info(f"Zakończono synchronizację dla {user.username}. Zapisano: {saved_activities_count}, Błędy: {failed_activities_count}.")
    return saved_activities_count, failed_activities_count


@login_required
def sync_garmin_activities(request):
    profile = request.user.profile
    if not profile.garmin_login or not profile.garmin_password:
        messages.error(request, "Brak danych logowania do Garmin Connect. Uzupełnij je w profilu.")
        logger.warning(f"User {request.user.username} attempted to sync without Garmin credentials.")
        return redirect("users_edit")

    logger.info(f"Starting Garmin sync for user {request.user.username}")
    try:
        client = Garmin(profile.garmin_login, profile.garmin_password)
        logger.info(f"Attempting to log in to Garmin Connect for user {request.user.username}")
        client.login()
        logger.info(f"Successfully logged in to Garmin Connect for user {request.user.username}")

    except GarminConnectAuthenticationError as e:
        messages.error(request, "Błąd uwierzytelniania w Garmin Connect. Sprawdź swój login i hasło.")
        logger.error(f"Garmin authentication failed for user {request.user.username}: {e}")
        return redirect("activities:activity_list")
    except (GarminConnectConnectionError, GarminConnectTooManyRequestsError) as e:
        messages.error(request, f"Błąd połączenia z serwerami Garmin: {e}")
        logger.error(f"Garmin connection error for user {request.user.username}: {e}")
        return redirect("activities:activity_list")
    except Exception as e:
        messages.error(request, f"Wystąpił nieoczekiwany błąd podczas logowania do Garmin: {e}")
        logger.error(f"Unexpected error during Garmin login for user {request.user.username}: {e}")
        return redirect("activities:activity_list")

    try:
        # Użyj nowej, wydzielonej funkcji do synchronizacji
        saved_activities, failed_activities = _sync_user_activities(request.user, client)

        # Komunikaty dla użytkownika
        if saved_activities > 0:
            messages.success(request, f"Pomyślnie zsynchronizowano i zapisano {saved_activities} nowych aktywności.")
        else:
            messages.info(request, "Brak nowych aktywności do zsynchronizowania.")

        if failed_activities > 0:
            messages.warning(request, f"Nie udało się zapisać {failed_activities} aktywności. Sprawdź logi serwera po więcej informacji.")

    except Exception as e:
        messages.error(request, f"Wystąpił nieoczekiwany błąd podczas pobierania aktywności z Garmin: {e}")
        logger.error(f"Unexpected error during Garmin activity fetch for user {request.user.username}: {e}")

    return redirect("activities:activity_list")


@login_required
def force_garmin_sync(request):
    """
    Zleca natychmiastową synchronizację danych Garmin dla bieżącego użytkownika (zadanie w tle).
    """
    if request.method == "POST":
        from django_q.tasks import async_task
        
        # Sprawdź czy użytkownik ma credentials
        profile = request.user.profile
        if not profile.garmin_login or not profile.garmin_password:
             messages.error(request, "Brak danych logowania do Garmin Connect. Uzupełnij profil.")
             return redirect("activities:activity_list")

        try:
            # Zlecamy zadanie w tle TYLKO dla tego użytkownika
            async_task('apps.activities.tasks.sync_single_user_garmin_data', request.user.id)
            messages.success(request, "Zlecono synchronizację w tle. Nowe aktywności pojawią się za chwilę.")
            
        except Exception as e:
            logger.error(f"Nie udało się zlecić zadania synchronizacji dla {request.user.username}: {e}")
            messages.error(request, "Wystąpił błąd podczas zlecania synchronizacji.")

    return redirect("activities:activity_list")


@login_required
def activity_list(request):
    activities_query = Activity.objects.filter(user=request.user).select_related('user').order_by('-start_time')

    # Pobieranie parametrów z GET request
    date_from_str = request.GET.get('date_from')
    date_to_str = request.GET.get('date_to')

    # Filtrowanie po dacie, jeśli parametry zostały podane
    if date_from_str:
        activities_query = activities_query.filter(start_time__date__gte=date_from_str)
    
    if date_to_str:
        activities_query = activities_query.filter(start_time__date__lte=date_to_str)

    # Pobierz obiekt harmonogramu następnej synchronizacji
    schedule = None
    try:
        schedule = Schedule.objects.filter(
            func='apps.activities.tasks.sync_all_users_garmin_data',
        ).order_by('next_run').first() # Sortujemy, aby dostać najbliższy w czasie

    except Exception as e:
        logger.error(f"Nie udało się pobrać harmonogramu synchronizacji Garmin: {e}")

    # Pobierz datę ostatniej udanej synchronizacji
    last_sync_time = None
    try:
        last_success = Success.objects.filter(
            func='apps.activities.tasks.sync_all_users_garmin_data'
        ).latest('stopped')
        last_sync_time = last_success.stopped
    except Success.DoesNotExist:
        pass # Brak udanych synchronizacji w historii
    except Exception as e:
        logger.error(f"Nie udało się pobrać daty ostatniej synchronizacji: {e}")

    context = {'activities': activities_query, 'schedule': schedule, 'last_sync_time': last_sync_time}
    return render(request, 'activities/activity_list.html', context)


@login_required
def activity_detail(request, activity_id):
    activity = get_object_or_404(Activity, activity_id=activity_id, user=request.user)

    is_tennis_studio = False
    # Sprawdź, czy użytkownik ma skonfigurowane dane logowania do Garmin
    has_garmin_credentials = bool(request.user.profile.garmin_login and request.user.profile.garmin_password)

    try:
        tennis_data = activity.tennis_data
        # Sprawdź, czy którekolwiek z pól ma wartość.
        # Używamy any() dla zwięzłości i czytelności
        if any(getattr(tennis_data, field.name) for field in TennisData._meta.get_fields() if field.name not in ['id', 'activity']):
            is_tennis_studio = True
    except TennisData.DoesNotExist:
        pass  # is_tennis_studio pozostaje False

    context = {
        'activity': activity, 
        'is_tennis_studio': is_tennis_studio,
        'has_garmin_credentials': has_garmin_credentials
    }
    return render(request, 'activities/activity_detail.html', context)


@login_required
def delete_activity(request, activity_id):
    """Usuwa aktywność. Dostępne tylko przez POST.""" # type: ignore
    if request.method == "POST":
        activity = get_object_or_404(Activity, activity_id=activity_id, user=request.user)
        activity_name = activity.activity_name
        activity.delete()
        messages.success(request, f"Aktywność '{activity_name}' została pomyślnie usunięta.")
        return redirect("activities:activity_list")
    
    # Jeśli nie POST, przekieruj na listę aktywności
    return redirect("activities:activity_list")


@login_required
def resync_activity(request, activity_id):
    """Ponownie pobiera i przetwarza dane dla pojedynczej aktywności."""
    if request.method != "POST":
        return redirect("activities:activity_detail", activity_id=activity_id)

    profile = request.user.profile
    if not profile.garmin_login or not profile.garmin_password:
        messages.error(request, "Brak danych logowania do Garmin Connect. Uzupełnij je w profilu.")
        return redirect("activities:activity_detail", activity_id=activity_id)

    activity = get_object_or_404(Activity, activity_id=activity_id, user=request.user)

    try:
        client = Garmin(profile.garmin_login, profile.garmin_password)
        client.login()

        # Jeśli to aktywność tenisowa, spróbuj pobrać dane z pliku FIT
        if activity.activity_type_key == "tennis_v2":
            logger.info(f"Ponowna synchronizacja danych FIT dla aktywności tenisowej {activity_id}.")
            if _process_fit_data(client, activity, activity_id):
                messages.success(request, "Pomyślnie zaktualizowano dane tenisowe dla aktywności.")
            else:
                messages.warning(request, "Nie udało się znaleźć dodatkowych danych tenisowych w pliku FIT.")
        else:
            messages.info(request, "Ta aktywność nie jest treningiem tenisowym, więc nie ma dodatkowych danych do synchronizacji.")

    except GarminConnectAuthenticationError:
        messages.error(request, "Błąd uwierzytelniania w Garmin Connect. Sprawdź swój login i hasło.")
    except (GarminConnectConnectionError, GarminConnectTooManyRequestsError) as e:
        messages.error(request, f"Błąd połączenia z serwerami Garmin: {e}")
    except Exception as e:
        messages.error(request, f"Wystąpił nieoczekiwany błąd podczas synchronizacji: {e}")
        logger.error(f"Błąd podczas ponownej synchronizacji aktywności {activity_id} dla {request.user.username}: {e}")

    return redirect("activities:activity_detail", activity_id=activity.activity_id)


@login_required
def edit_activity_name(request, activity_id):
    """Zmienia nazwę aktywności. Dostępne tylko przez POST."""
    activity = get_object_or_404(Activity, activity_id=activity_id, user=request.user)

    if request.method == "POST":
        new_name = request.POST.get('activity_name', '').strip()
        if new_name:
            old_name = activity.activity_name
            activity.activity_name = new_name
            activity.save(update_fields=['activity_name'])
            messages.success(request, f"Zmieniono nazwę aktywności z '{old_name}' na '{new_name}'.")
        else:
            messages.error(request, "Nazwa aktywności nie może być pusta.")
    
    return redirect("activities:activity_detail", activity_id=activity.activity_id)


@login_required
def garmin_disconnect(request):
    """Usuwa poświadczenia Garmin z profilu użytkownika."""
    profile = request.user.profile
    if profile.garmin_login or profile.garmin_password:
        profile.garmin_login = ""
        profile.garmin_password = ""
        profile.save()
        messages.success(request, "Pomyślnie rozłączono konto Garmin Connect.")
    
    return redirect("users_edit")