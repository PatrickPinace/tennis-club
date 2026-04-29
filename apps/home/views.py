from datetime import timedelta
from django.shortcuts import render, redirect
from django.views.generic import TemplateView

class PrivacyPolicyView(TemplateView):
    template_name = "home/privacy_policy.html"
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponseNotFound, HttpResponseServerError

# Importy z Twoich aplikacji
from apps.matches.models import Match
from apps.friends.models import Friend
from apps.tournaments.models import Tournament, TournamentsMatch

def custom_404(request, exception):
    return render(request, '404.html', {}, status=404)

def custom_500(request):
    return render(request, '500.html', {}, status=500)


def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'home/home.html', {})

def about_author(request):
    """
    View for the 'About Author' page.
    """
    # Przygotowanie danych o lokalizacji (Mielec)
    # Można tu dodać więcej szczegółów, np. współrzędne, nazwę klubu itp.
    context = {
        'location': {
            'name': 'Mielec',
            'description': 'Miasto, w którym narodziła się moja pasja do tenisa ziemnego.',
            'query': 'Mielec, Poland'  # Zapytanie do mapy
        }
    }
    return render(request, 'home/about_author.html', context)

@login_required(login_url='home')
def dashboard(request):
    current_user = request.user
    now = timezone.now()
    seven_days_ago = now - timedelta(days=7)
    five_minutes_ago = now - timedelta(minutes=5)

    # ---------------------------------------------------------
    # KROK 1: Znajomi (Pobranie ID i Usernames)
    # ---------------------------------------------------------
    # Pobieramy ID oraz nazwy użytkowników znajomych w jednym zapytaniu.
    # Potrzebujemy 'friend__username' do kluczy cache.
    friends_queryset = Friend.objects.filter(user=current_user).select_related('friend')
    
    # Tworzymy listy pomocnicze
    friend_ids = []
    friend_username_map = {} # Mapa {username: user_obj} do szybkiego dostępu
    
    for f in friends_queryset:
        friend_ids.append(f.friend_id)
        friend_username_map[f.friend.username] = f.friend

    # ---------------------------------------------------------
    # KROK 2: Status Online (Zoptymalizowane cache.get_many)
    # ---------------------------------------------------------
    # Zamiast pytać cache w pętli N razy, generujemy listę kluczy i pytamy raz.
    cache_keys = [f'seen_{username}' for username in friend_username_map.keys()]
    cache_results = cache.get_many(cache_keys)
    
    online_users = []
    for username, user_obj in friend_username_map.items():
        last_seen = cache_results.get(f'seen_{username}')
        if last_seen and last_seen > five_minutes_ago:
            online_users.append(user_obj)

    # ---------------------------------------------------------
    # KROK 3: Ostatnie mecze znajomych (Singiel i Debel)
    # ---------------------------------------------------------
    # Używamy Q objects. Wykluczamy mecze, w których my braliśmy udział, 
    # żeby widzieć tylko aktywność znajomych.
    
    last_singles = Match.objects.filter(
        Q(p1__in=friend_ids) | Q(p2__in=friend_ids),
        match_double=False
    ).exclude(
        Q(p1=current_user) | Q(p2=current_user)
    ).select_related('p1', 'p2').order_by('-match_date')[:5]

    last_doubles = Match.objects.filter(
        Q(p1__in=friend_ids) | Q(p2__in=friend_ids) | Q(p3__in=friend_ids) | Q(p4__in=friend_ids),
        match_double=True
    ).exclude(
        Q(p1=current_user) | Q(p2=current_user) | Q(p3=current_user) | Q(p4=current_user)
    ).select_related('p1', 'p2', 'p3', 'p4').order_by('-match_date')[:5]

    # ---------------------------------------------------------
    # KROK 4: Użytkownicy (Logowania i Rejestracje)
    # ---------------------------------------------------------
    recent_logins = User.objects.filter(
        last_login__isnull=False,
        last_login__gte=seven_days_ago
    ).exclude(is_superuser=True).exclude(id=current_user.id).order_by('-last_login')[:3]
    
    # Optymalizacja: pobieramy cache dla 'recent_logins' też przez get_many jeśli to konieczne,
    # ale przy limicie [:3] pętla jest akceptowalna.
    for user in recent_logins:
        last_seen = cache.get(f'seen_{user.username}')
        user.last_activity = last_seen if last_seen else user.last_login

    recent_registrations = User.objects.filter(
        date_joined__gte=seven_days_ago
    ).exclude(is_superuser=True).exclude(id=current_user.id).order_by('-date_joined')[:3]

    # ---------------------------------------------------------
    # KROK 5: Turnieje
    # ---------------------------------------------------------
    ongoing_tournaments = Tournament.objects.filter(
        status__in=[
            Tournament.Status.REGISTRATION.value,
            Tournament.Status.SCHEDULED.value,
            Tournament.Status.ACTIVE.value
        ]
    ).order_by('-start_date')

    last_tournament_matches = TournamentsMatch.objects.select_related(
        'tournament', 'participant1', 'participant2', 'winner'
    ).filter(
        status=TournamentsMatch.Status.COMPLETED.value
    ).order_by('-scheduled_time')[:3]

    in_progress_matches = TournamentsMatch.objects.select_related(
        'tournament', 'participant1', 'participant2'
    ).filter(
        status=TournamentsMatch.Status.IN_PROGRESS.value
    ).order_by('-scheduled_time')

    # Licznik kart
    tournament_card_count = (
        (1 if ongoing_tournaments.exists() else 0) +
        (1 if in_progress_matches.exists() else 0) +
        (1 if last_tournament_matches.exists() else 0)
    )

    # ---------------------------------------------------------
    # KROK 6: Automatyczna aktualizacja statusu (Lazy Update)
    # ---------------------------------------------------------
    # UWAGA: To rozwiązanie działa tylko, gdy ktoś odwiedza dashboard.
    # W produkcji lepiej użyć Celery/Cron.
    matches_to_start = TournamentsMatch.objects.filter(
        status=TournamentsMatch.Status.SCHEDULED.value,
        scheduled_time__lte=now
    )
    if matches_to_start.exists():
        matches_to_start.update(status=TournamentsMatch.Status.IN_PROGRESS.value)

    context = {
        'last_singles': last_singles,
        'last_doubles': last_doubles,
        'recent_logins': recent_logins,
        'recent_registrations': recent_registrations,
        'ongoing_tournaments': ongoing_tournaments,
        'online_users': online_users,
        'last_tournament_matches': last_tournament_matches,
        'in_progress_matches': in_progress_matches,
        'tournament_card_count': tournament_card_count,
    }

    return render(request, 'home/dashboard.html', context)
