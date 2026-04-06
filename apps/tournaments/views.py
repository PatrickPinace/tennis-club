from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from typing import Any, cast
from django.views.decorators.http import require_POST
import math
from django.db.models import Q, Max, Count, Case, When, Value, IntegerField
from django.utils import timezone
import random, itertools
from django.http import JsonResponse

from .models import Tournament, RoundRobinConfig, EliminationConfig, LadderConfig
from .models import (Participant, TeamMember, ChallengeRejection, TournamentsMatch, MatchScoreHistory,
                     MatchReaction, AmericanoConfig, SwissSystemConfig)
from .forms import (TournamentForm, RoundRobinConfigForm, EliminationConfigForm, LadderConfigForm,
                     AmericanoConfigForm, SwissSystemConfigForm, AmericanoMatchForm, ParticipantMatchForm, ParticipantForm,
                     TeamMemberForm, TournamentsMatchForm)
from .tools import (calculate_round_robin_standings, calculate_americano_standings, 
                    annotate_match_permissions)
from .swiss_logic import (generate_swiss_matches_initial, generate_next_swiss_round, 
                          get_participant_standings_swiss)

from notifications.views import add_notification, notify_user
from chats.forms import MessageForm
from chats.models import TournamentMatchChatMessage, TournamentMatchChatImage


@login_required
def create_tournament(request):
    if request.method == 'POST':
        form = TournamentForm(request.POST)
        if form.is_valid():
            tournament = form.save(commit=False)
            tournament.created_by = request.user
            tournament.save()

            # Utwórz domyślną konfigurację w zależności od typu turnieju, jeśli nie istnieje
            config_url = None
            if tournament.tournament_type == 'RND':
                if not hasattr(tournament, 'round_robin_config'):
                    RoundRobinConfig.objects.create(tournament=tournament)
                config_url = 'tournaments:edit_roundrobin_config'
            elif tournament.tournament_type == 'SGL':
                if not hasattr(tournament, 'elimination_config'):
                    EliminationConfig.objects.create(tournament=tournament)
                config_url = 'tournaments:edit_elimination_config'
            elif tournament.tournament_type == 'DBE':
                if not hasattr(tournament, 'config'):
                    EliminationConfig.objects.create(tournament=tournament)
                config_url = 'tournaments:edit_double_elimination_config'
            elif tournament.tournament_type == 'LDR':
                if not hasattr(tournament, 'ladder_config'):
                    LadderConfig.objects.create(tournament=tournament)
                config_url = 'tournaments:edit_ladder_config'
            elif tournament.tournament_type == 'AMR':
                if not hasattr(tournament, 'americano_config'):
                    AmericanoConfig.objects.create(tournament=tournament)
                config_url = 'tournaments:edit_americano_config'
            elif tournament.tournament_type == 'SWS':
                if not hasattr(tournament, 'swiss_system_config'):
                    SwissSystemConfig.objects.create(tournament=tournament)
                config_url = 'tournaments:edit_swiss_config'
            messages.success(request, 'Turniej został utworzony. Skonfiguruj szczegóły poniżej.')
            if config_url:
                return redirect(config_url, pk=tournament.pk)
            return redirect('tournaments:manage')
        else:
            # Nie twórz nowego formularza, przekaż istniejący z błędami do szablonu
            messages.error(request, 'W formularzu wystąpiły błędy. Sprawdź pola i spróbuj ponownie.')
            # Renderuj szablon ponownie z tym samym formularzem, który zawiera błędy
            return render(request, 'tournaments/tournament_form.html', {'form': form})

    # Jeśli request.method to nie POST, to jest to GET
    now = timezone.now()
    start_time = now.replace(hour=8, minute=0, second=0, microsecond=0)
    end_time = now.replace(hour=15, minute=0, second=0, microsecond=0)

    initial_data = {
        'status': Tournament.Status.DRAFT,
        'start_date': start_time.strftime('%Y-%m-%dT%H:%M'),
        'end_date': end_time.strftime('%Y-%m-%dT%H:%M'),
    }
    form = TournamentForm(initial=initial_data)
    return render(request, 'tournaments/tournament_form.html', {'form': form})


@login_required
@require_POST
def delete_tournament(request, pk):
    """
    Pozwala organizatorowi na usunięcie turnieju, jeśli jego status to DRF (Szkic) lub REG (Zarejestrowany).
    """
    tournament = get_object_or_404(Tournament, pk=pk)

    # 1. Sprawdzenie, czy użytkownik jest organizatorem
    if request.user != tournament.created_by and not request.user.is_staff:
        messages.error(request, 'Brak uprawnień do usunięcia tego turnieju.')
        return redirect('tournaments:manage')

    # 2. Sprawdzenie aktualnego statusu
    if tournament.is_deletable:
        tournament_name = tournament.name
        tournament.delete()
        messages.success(request, f'Turniej "{tournament_name}" został usunięty.')
    else:
        messages.error(request, f'Turniej "{tournament.name}" o statusie "{tournament.get_status_display()}" nie może zostać usunięty.')

    return redirect('tournaments:manage')


@login_required
def manage(request):
    query = request.GET.get('q')
    tournaments = Tournament.objects.all()

    if query:
        tournaments = tournaments.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(created_by__username__icontains=query) |
            Q(created_by__first_name__icontains=query) |
            Q(created_by__last_name__icontains=query)
        )

    tournaments = tournaments.order_by('-end_date')

    # Zamiana na listę, aby zachować adnotacje dodawane w pętli poniżej
    # oraz umożliwić ponowne iterowanie w szablonie bez zapytania do DB
    tournaments_list = list(tournaments)

    # Adnotacja każdego turnieju flagami pomocniczymi używanymi przez szablon,
    # aby uniknąć wywoływania metod queryset z argumentami wewnątrz szablonów.
    # Dzięki temu szablon pozostaje czysty, a logika przeniesiona jest do widoku.
    for t in tournaments_list:
        # Dla statycznych analizatorów typów rzutujemy na Any przed dodaniem dynamicznych atrybutów
        t_any = cast(Any, t)

        # Ustaw domyślne wartości
        t_any.user_is_organizer = (request.user == t.created_by)
        t_any.user_is_participant = False
        t_any.can_request_join = False

        if request.user.is_authenticated:
            if Participant.objects.filter(tournament=t, user=request.user).exists():
                t_any.user_is_participant = True
            # Użytkownik może dołączyć, jeśli nie jest organizatorem, nie jest już uczestnikiem,
            # a turniej jest otwarty na rejestrację.
            elif not t_any.user_is_organizer and t.is_open_for_registration:
                t_any.can_request_join = True

    context = {
        'tournaments': tournaments_list,
        'search_query': query
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'tournaments/partials/manage_list.html', context)

    return render(request, 'tournaments/manage.html', context)


def tournament_details_round_robin(request, pk):
    """
    Wyświetla szczegóły turnieju Round Robin, w tym tabelę wyników i listę meczów.
    """
    tournament = get_object_or_404(Tournament, pk=pk, tournament_type=Tournament.TournamentType.ROUND_ROBIN.value)
    participants = tournament.participants.filter(status__in=['ACT', 'REG'])
    # Używamy select_related, aby zoptymalizować zapytania i uniknąć problemu N+1
    matches = tournament.matches.select_related('participant1', 'participant2', 'winner').order_by('round_number', 'match_index')

    user_reactions_dict = {}
    if request.user.is_authenticated:
        user_reactions = MatchReaction.objects.filter(
            match__in=matches,
            user=request.user
        ).values_list('match_id', 'emoji')
        user_reactions_dict = {match_id: emoji for match_id, emoji in user_reactions}

    # --- POPRAWKA: Sortowanie meczów, aby mecze użytkownika były na górze ---
    if request.user.is_authenticated:
        user_participant = participants.filter(user=request.user).first()
        if user_participant:
            # Dodajemy adnotację, która przypisze 0 do meczów użytkownika i 1 do pozostałych,
            # a następnie sortujemy najpierw po tej adnotacji.
            matches = matches.annotate(
                is_user_match=Case(
                    When(Q(participant1=user_participant) | Q(participant2=user_participant), then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField()
                )
            ).order_by('is_user_match', 'round_number', 'match_index')
    
    # Dodajemy flagi pozwolenia (can_edit, user_reaction) przy użyciu helpera z tools
    annotate_match_permissions(matches, request.user, tournament)

    # Pobierz konfigurację lub utwórz domyślną, jeśli nie istnieje, aby uniknąć błędów
    config, created = RoundRobinConfig.objects.get_or_create(tournament=tournament)
    if created:
        messages.info(request, "Utworzono domyślną konfigurację dla tego turnieju.")

    # Obliczanie tabeli wyników przy użyciu helpera z tools
    standings_list = calculate_round_robin_standings(tournament, participants, config)

    # --- Statystyki Turnieju ---
    stats = {}
    stats['completed_matches_count'] = matches.filter(status=TournamentsMatch.Status.COMPLETED.value).count()

    if standings_list:
        stats['top_winner'] = max(standings_list, key=lambda x: x['wins'])
        stats['top_set_winner'] = max(standings_list, key=lambda x: x['sets_won'])
        stats['top_game_winner'] = max(standings_list, key=lambda x: x['games_won'])
    else:
        stats['top_winner'] = None
        stats['top_set_winner'] = None
        stats['top_game_winner'] = None

    context = {
        'tournament': tournament,
        'matches': matches,
        'standings': standings_list,
        'stats': stats,
    }
    return render(request, 'tournaments/tournament_details_round_robin.html', context)


def tournament_details_single_elimination(request, pk):
    """
    Wyświetla szczegóły turnieju pucharowego, w tym drabinkę turniejową.
    """
    tournament = get_object_or_404(Tournament, pk=pk, tournament_type=Tournament.TournamentType.SINGLE_ELIMINATION.value)
    
    # Używamy select_related, aby zoptymalizować zapytania
    matches = list(tournament.matches.select_related(
        'participant1', 'participant2', 'winner'
    ).order_by('round_number', 'match_index'))

    # Dodajemy flagi pozwolenia (can_edit, user_reaction) przy użyciu helpera z tools
    annotate_match_permissions(matches, request.user, tournament)

    # Grupujemy mecze według numeru rundy
    rounds = {}
    for match in matches:
        # --- NOWOŚĆ: Obliczanie wyniku w setach dla każdego meczu ---
        if match.status == TournamentsMatch.Status.COMPLETED.value and match.winner:
            set_scores = []
            for i in range(1, 4): # Iteruj po setach 1, 2, 3
                p1_score = getattr(match, f'set{i}_p1_score', None)
                p2_score = getattr(match, f'set{i}_p2_score', None)

                if p1_score is not None and p2_score is not None:
                    # Wyświetlaj wynik tylko, jeśli nie jest to 0-0
                    if p1_score > 0 or p2_score > 0:
                        set_scores.append((p1_score, p2_score))

            # Zapisz wyniki setów jako nowe atrybuty obiektu meczu
            match.set_scores = set_scores
        # --- Koniec nowej logiki ---

        if match.round_number == 0: continue # Wykluczamy mecz o 3. miejsce z głównej drabinki
        if match.round_number not in rounds:
            rounds[match.round_number] = []
        rounds[match.round_number].append(match)

    context = {
        'tournament': tournament,
        'rounds': rounds,
        'matches_exist': bool(matches)
    }

    # Sprawdź, czy istnieje mecz o 3. miejsce (ma numer rundy 0)
    # Sprawdź, czy istnieje mecz o 3. miejsce (ma numer rundy 0)
    if tournament.elimination_config and tournament.elimination_config.third_place_match:
        # Pobieramy z listy matches, która została już przetworzona przez annotate_match_permissions
        third_place_match = next((m for m in matches if m.round_number == 0), None)
        context['third_place_match'] = third_place_match

    return render(request, 'tournaments/tournament_details_single_elimination.html', context)


def tournament_details_double_elimination(request, pk):
    """
    Wyświetla szczegóły turnieju podwójnej eliminacji (Double Elimination).
    Osoby przegrywające trafiają do drabinki przegranych.
    Na końcu rozgrywany jest Wielki Finał.
    """
    tournament = get_object_or_404(Tournament, pk=pk, tournament_type=Tournament.TournamentType.DOUBLE_ELIMINATION.value)

    # Pobieramy mecze posortowane po rundzie i indeksie
    matches = tournament.matches.select_related(
        'participant1', 'participant2', 'winner'
    ).order_by('round_number', 'match_index')

    # Dodajemy flagi pozwolenia
    annotate_match_permissions(matches, request.user, tournament)

    # Rozdziel mecze na drabinki
    winners_rounds = {}
    losers_rounds = {}
    grand_final_match = None

    for match in matches:
        # Logika wyników setów
        if match.status == TournamentsMatch.Status.COMPLETED.value and match.winner:
            set_scores = []
            for i in range(1, 4):
                p1_score = getattr(match, f'set{i}_p1_score', None)
                p2_score = getattr(match, f'set{i}_p2_score', None)
                if p1_score is not None and p2_score is not None:
                    if p1_score > 0 or p2_score > 0:
                        set_scores.append((p1_score, p2_score))
            match.set_scores = set_scores

        # Klasyfikacja meczów do odpowiednich drabinek
        if match.round_number == 99:
            grand_final_match = match
        elif match.match_index >= 1000:
            if match.round_number not in losers_rounds:
                losers_rounds[match.round_number] = []
            losers_rounds[match.round_number].append(match)
        else:
            if match.round_number not in winners_rounds:
                winners_rounds[match.round_number] = []
            winners_rounds[match.round_number].append(match)

    context = {
        'tournament': tournament,
        'winners_rounds': winners_rounds,
        'losers_rounds': losers_rounds,
        'matches_exist': matches.exists(),
        'grand_final': grand_final_match,
        'double_elimination': True # Flaga dla szablonu
    }

    return render(request, 'tournaments/tournament_details_double_elimination.html', context)


def tournament_details_americano(request, pk):
    """
    Wyświetla szczegóły turnieju Americano, w tym tabelę wyników i listę meczów.
    """
    tournament = get_object_or_404(
        Tournament.objects.select_related('americano_config'),
        pk=pk,
        tournament_type=Tournament.TournamentType.AMERICANO.value
    )
    
    participants = tournament.participants.filter(status__in=['ACT', 'REG'])
    matches = tournament.matches.select_related(
        'participant1', 'participant2', 'participant3', 'participant4'
    ).order_by('round_number', 'match_index')

    # Dodajemy flagę 'can_edit' do każdego meczu, aby uprościć logikę w szablonie
    annotate_match_permissions(matches, request.user, tournament)

    standings_list = calculate_americano_standings(tournament)

    # Jeśli to Mexicano i nikt jeszcze nie zdobył punktów, posortuj według numeru rozstawienia (seed)
    is_mexicano = tournament.americano_config and tournament.americano_config.scheduling_type == 'DYNAMIC'
    no_points_scored = all(s['points'] == 0 for s in standings_list)

    if is_mexicano and no_points_scored:
        # Sortuj rosnąco po seed_number, traktując None jako dużą liczbę, aby umieścić na końcu
        standings_list.sort(key=lambda x: (x['participant'].seed_number is None, x['participant'].seed_number))

    # --- Statystyki Turnieju ---
    stats = {}
    stats['completed_matches_count'] = matches.filter(status=TournamentsMatch.Status.COMPLETED.value).count()

    if standings_list:
        stats['top_scorer'] = standings_list[0] # Lista jest już posortowana po punktach
        stats['most_matches_player'] = max(standings_list, key=lambda x: x['matches_played'])
    else:
        stats['top_scorer'] = None
        stats['most_matches_player'] = None

    # Grupujemy mecze według numeru rundy
    rounds = {r: list(m) for r, m in itertools.groupby(matches, key=lambda x: x.round_number)}

    # Znajdź numer bieżącej rundy do rozwinięcia w akordeonie
    current_round_number = 1
    if matches:
        # Znajdź pierwszy mecz, który nie jest zakończony
        first_active_match = matches.exclude(status=TournamentsMatch.Status.COMPLETED.value).first()
        if first_active_match:
            current_round_number = first_active_match.round_number
        else:
            # Jeśli wszystkie mecze są zakończone, rozwiń ostatnią rundę
            last_match = matches.last()
            if last_match:
                current_round_number = last_match.round_number

    context = {
        'tournament': tournament,
        'standings': standings_list,
        'rounds': rounds,
        'stats': stats,
        'current_round_number': current_round_number,
    }
    return render(request, 'tournaments/tournament_details_americano.html', context)


def tournament_details_ladder(request, pk):
    """
    Wyświetla szczegóły turnieju drabinkowego, w tym ranking.
    """
    tournament = get_object_or_404(
        Tournament.objects.select_related('ladder_config'),
        pk=pk,
        tournament_type=Tournament.TournamentType.LADDER.value
    )
    
    participants = list(tournament.participants.filter(
        status__in=['ACT', 'REG']
    ).order_by('seed_number'))

    active_statuses = [TournamentsMatch.Status.WAITING.value, TournamentsMatch.Status.SCHEDULED.value, TournamentsMatch.Status.IN_PROGRESS.value]
    active_matches = TournamentsMatch.objects.filter(tournament=tournament, status__in=active_statuses)
    
    busy_participant_ids = set()
    busy_participant_ids.update(active_matches.values_list('participant1_id', flat=True))
    busy_participant_ids.update(active_matches.values_list('participant2_id', flat=True))
    
    challenged_participant_ids = set(active_matches.values_list('participant2_id', flat=True))

    for p in participants:
        p.is_in_active_match = p.id in busy_participant_ids
        p.is_being_challenged = p.id in challenged_participant_ids
        p.has_recent_match = False
        p.has_rejected_us = False

    # --- POPRAWKA ---
    # Zamiast szukać ostatniego zakończonego meczu w całym turnieju,
    # sprawdzamy mecze zakończone tylko w bieżącej, najwyższej rundzie.
    # To zapobiega blokowaniu wyzwań po resecie drabinki przez admina.
    current_max_round = tournament.matches.aggregate(max_round=Max('round_number')).get('max_round')

    completed_matches = []
    if current_max_round:
        completed_matches = TournamentsMatch.objects.filter(
            tournament=tournament,
            status=TournamentsMatch.Status.COMPLETED.value,
            round_number=current_max_round
        )

    active_statuses_for_sort = [TournamentsMatch.Status.WAITING.value, TournamentsMatch.Status.SCHEDULED.value, TournamentsMatch.Status.IN_PROGRESS.value]

    # --- POPRAWKA: Wyklucz mecze techniczne (TBA vs TBA) ---
    matches = tournament.matches.filter(
        Q(participant1__isnull=False) | Q(participant2__isnull=False)
    ).select_related(
        'participant1', 'participant2', 'winner'
    ).annotate(
        status_order=Case(
            When(status__in=active_statuses_for_sort, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by('status_order', '-round_number', '-scheduled_time', '-pk')

    if request.user.is_authenticated:
        # --- NOWOŚĆ: Pobierz reakcje użytkownika dla wyświetlanych meczów ---
        # UWAGA: annotate_match_permissions obsługuje reakcje użytkownika wewnętrznie,
        # ale musimy przekazać queryset lub listę.
        pass

    # Dodajemy flagi pozwolenia
    annotate_match_permissions(matches, request.user, tournament)

    # --- Statystyki Turnieju ---
    stats = {}
    
    # Liczba rozegranych meczów
    stats['completed_matches_count'] = tournament.matches.filter(status=TournamentsMatch.Status.COMPLETED.value).count()
    stats['total_participants'] = len(participants)

    # Gracz z największą liczbą zwycięstw
    winner_stats = TournamentsMatch.objects.filter(
        tournament=tournament, status=TournamentsMatch.Status.COMPLETED.value, winner__isnull=False
    ).values('winner__display_name').annotate(wins=Count('winner')).order_by('-wins').first()
    stats['top_winner'] = winner_stats

    # Gracz, który rzucił najwięcej wyzwań (participant1)
    challenger_stats = TournamentsMatch.objects.filter(
        tournament=tournament, participant1__isnull=False
    ).values('participant1__display_name').annotate(challenges=Count('participant1')).order_by('-challenges').first()
    stats['top_challenger'] = challenger_stats

    # Gracz, który był najczęściej wyzywany (participant2)
    challenged_stats = TournamentsMatch.objects.filter(
        tournament=tournament, participant2__isnull=False
    ).values('participant2__display_name').annotate(challenges=Count('participant2')).order_by('-challenges').first()
    stats['top_challenged'] = challenged_stats
    # --- Koniec Statystyk ---

    user_participant = None
    challengeable_participants = []
    can_challenge = False

    if request.user.is_authenticated:
        try:
            user_participant = next((p for p in participants if p.user == request.user), None)
        except Participant.DoesNotExist:
            user_participant = None

    if user_participant:
        config = tournament.ladder_config
        can_challenge = not user_participant.is_in_active_match
        if config and user_participant.seed_number is not None:
            min_rank_to_challenge = max(1, user_participant.seed_number - config.challenge_range)
            challengeable_participants = [p for p in participants if p.seed_number is not None and 
                                          min_rank_to_challenge <= p.seed_number < user_participant.seed_number]
            
            recent_opponent_ids = set()
            for m in completed_matches:
                if m.participant1_id == user_participant.id:
                    recent_opponent_ids.add(m.participant2_id)
                elif m.participant2_id == user_participant.id:
                    recent_opponent_ids.add(m.participant1_id)
            for p in participants:
                p.has_recent_match = p.id in recent_opponent_ids
            
            rejected_by_ids = set(ChallengeRejection.objects.filter(
                tournament=tournament,
                challenger_participant=user_participant
            ).values_list('rejecting_participant_id', flat=True))
            for p in participants:
                p.has_rejected_us = p.id in rejected_by_ids

    context = {
        'tournament': tournament,
        'participants': participants,
        'matches': matches,
        'user_participant': user_participant,
        'challengeable_participants': challengeable_participants,
        'can_challenge': can_challenge,
        'stats': stats,
    }
    return render(request, 'tournaments/tournament_details_ladder.html', context)


def tournament_details_swiss(request, pk):
    """
    Wyświetla szczegóły turnieju systemem szwajcarskim.
    Dzieli widok na fazę grupową (Swiss Stage) z grupowaniem po bilansie
    i fazę pucharową (Playoff Stage).
    """
    tournament = get_object_or_404(
        Tournament.objects.select_related('swiss_system_config'),
        pk=pk,
        tournament_type=Tournament.TournamentType.SWISS.value
    )
    
    config = tournament.swiss_system_config
    if not config:
        # Fallback na wypadek braku konfiguracji
        SwissSystemConfig.objects.create(tournament=tournament)
        config = tournament.swiss_system_config

    participants = tournament.participants.filter(status__in=['ACT', 'REG'])
    matches_qs = tournament.matches.select_related(
        'participant1', 'participant2', 'winner'
    ).order_by('round_number', 'match_index')
    
    matches = list(matches_qs)
    annotate_match_permissions(matches, request.user, tournament)

    # Obliczanie wyniku w setach dla każdego meczu (potrzebne do match_content.html)
    for match in matches:
        if match.status == TournamentsMatch.Status.COMPLETED.value:
            set_scores = []
            for i in range(1, 4): # Iteruj po setach 1, 2, 3
                p1_score = getattr(match, f'set{i}_p1_score', None)
                p2_score = getattr(match, f'set{i}_p2_score', None)

                if p1_score is not None and p2_score is not None:
                     # Wyświetlaj wynik, nawet 0-0 jeśli set został rozegrany (zakładamy że jeśli not None to grali)
                     set_scores.append((p1_score, p2_score))

            if set_scores:
                match.set_scores = set_scores
    
    # --- 1. Podział na Swiss Stage i Playoff Stage ---
    swiss_matches = [m for m in matches if m.round_number <= config.number_of_rounds]
    playoff_matches = [m for m in matches if m.round_number > config.number_of_rounds]
    
    # --- 2. Przygotowanie danych dla Swiss Stage (Faza Grupowa) ---
    # Musimy pogrupować mecze w każdej rundzie według bilansu (Scores) PRZED tą rundą.
    # Np. w Rundzie 2, mecz gracza z bilansem 1-0 i gracza 1-0 powinien trafić do grupy "1-0".
    
    # Słownik do śledzenia bieżącego bilansu uczestników podczas iteracji po rundach
    # structure: participant_id -> {'wins': 0, 'losses': 0}
    current_standings = {p.id: {'wins': 0, 'losses': 0} for p in participants}
    
    swiss_rounds = []
    
    # Grupujemy mecze po rundach
    rounds_data = {}
    for m in swiss_matches:
        if m.round_number not in rounds_data:
            rounds_data[m.round_number] = []
        rounds_data[m.round_number].append(m)
        
    # Iterujemy po rundach od 1 do Config.number_of_rounds (lub max dostępnej)
    max_round = max(rounds_data.keys()) if rounds_data else config.number_of_rounds
    
    for r in range(1, max_round + 1):
        round_matches = rounds_data.get(r, [])
        
        # Grupy bilansowe w tej rundzie: label -> list of matches
        # np. "1-0" -> [match1, match2]
        score_groups_map = {}
        
        for match in round_matches:
            # Ustal bilans dla tej grupy na podstawie participant1 (high seed usually)
            # W idealnym parowaniu Swiss, obaj gracze mają ten sam bilans.
            # Weźmy bilans participant1 jako reprezentatywny dla grupy.
            if match.participant1:
                p_stats = current_standings.get(match.participant1.id, {'wins': 0, 'losses': 0})
                score_label = f"{p_stats['wins']}-{p_stats['losses']}"
            else:
                score_label = "0-0" # Dla bye w pierwszej rundzie lub błędów
            
            if score_label not in score_groups_map:
                score_groups_map[score_label] = []
            score_groups_map[score_label].append(match)
            
        # Aktualizuj current_standings na podstawie WYNIKÓW tej rundy (dla następnej iteracji)
        for match in round_matches:
            if match.winner:
                # Winner
                if match.winner_id in current_standings:
                    current_standings[match.winner_id]['wins'] += 1
                
                # Loser
                loser = None
                if match.participant1 and match.participant1 != match.winner:
                    loser = match.participant1
                elif match.participant2 and match.participant2 != match.winner:
                    loser = match.participant2
                
                if loser and loser.id in current_standings:
                    current_standings[loser.id]['losses'] += 1
        
        # Przekształć mapę grup na listę posortowaną (najpierw najwięcej wygranych)
        sorted_groups = []
        def parse_score(label):
            try:
                w, l = map(int, label.split('-'))
                return (-w, l)
            except:
                return (0, 0)
                
        for label in sorted(score_groups_map.keys(), key=parse_score):
            sorted_groups.append({
                'score_label': label,
                'matches': score_groups_map[label]
            })
            
        swiss_rounds.append({
            'round_number': r,
            'groups': sorted_groups
        })

    # --- 3. Przygotowanie danych dla Playoff Stage (Faza Pucharowa) ---
    playoff_rounds = {}
    for match in playoff_matches:
        if match.round_number not in playoff_rounds:
            playoff_rounds[match.round_number] = []
        playoff_rounds[match.round_number].append(match)

    # --- 4. Tabela Wyników (Końcowa / Aktualna) ---
    standings_dict = get_participant_standings_swiss(tournament)
    standings_list = list(standings_dict.values())
    standings_list.sort(key=lambda x: (
        x['wins'], 
        -x['losses'], 
        -(x['participant'].seed_number if x['participant'].seed_number is not None else 9999)
    ), reverse=True)

    # Statystyki
    stats = {}
    stats['completed_matches_count'] = len([m for m in matches if m.status == TournamentsMatch.Status.COMPLETED.value])
    if standings_list:
        stats['top_winner'] = standings_list[0]
    
    context = {
        'tournament': tournament,
        'standings': standings_list,
        'swiss_rounds': swiss_rounds,       # Nowa struktura dla Swiss
        'playoff_rounds': playoff_rounds,   # Struktura dla Playoff
        'has_playoff': bool(playoff_matches),
        'stats': stats,
        'config': config
    }
    
    return render(request, 'tournaments/tournament_details_swiss.html', context)


@login_required
def edit_roundrobin_config(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    if request.user != tournament.created_by and not request.user.is_staff:
        messages.error(request, 'Tylko organizator może edytować konfigurację tego turnieju.')
        return redirect('tournaments:manage')

    if tournament.tournament_type != 'RND':
        messages.error(request, 'Konfiguracja Round Robin dostępna tylko dla turniejów typu Round Robin.')
        return redirect('tournaments:manage')

    config = getattr(tournament, 'round_robin_config', None)

    if request.method == 'POST':
        form = RoundRobinConfigForm(request.POST, instance=config)
        if form.is_valid():
            status = form.cleaned_data.get('status')
            if status:
                tournament.status = status
                tournament.save()

            rc = form.save(commit=False)
            rc.tournament = tournament
            rc.save()
            messages.success(request, 'Konfiguracja Round Robin została zapisana.')
            return redirect('tournaments:manage')
        else:
            messages.error(request, 'W formularzu wystąpiły błędy. Popraw i spróbuj ponownie.')
    else:
        form = RoundRobinConfigForm(instance=config)

    return render(request, 'tournaments/roundrobin_config_form.html', {'form': form, 'tournament': tournament})


@login_required
def edit_elimination_config(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    if request.user != tournament.created_by and not request.user.is_staff:
        messages.error(request, 'Tylko organizator może edytować konfigurację tego turnieju.')
        return redirect('tournaments:manage')

    if tournament.tournament_type not in ['SGL', 'DBE']:
        messages.error(request, 'Konfiguracja eliminacji dostępna tylko dla turniejów pucharowych.')
        return redirect('tournaments:manage')

    config = getattr(tournament, 'elimination_config', None)

    if request.method == 'POST':
        form = EliminationConfigForm(request.POST, instance=config)
        if form.is_valid():
            status = form.cleaned_data.get('status')
            if status:
                tournament.status = status
                tournament.save()

            ec = form.save(commit=False)
            ec.tournament = tournament
            ec.save()
            messages.success(request, 'Konfiguracja eliminacji została zapisana.')
            return redirect('tournaments:manage')
        else:
            messages.error(request, 'W formularzu wystąpiły błędy. Popraw i spróbuj ponownie.')
    else:
        form = EliminationConfigForm(instance=config)

    return render(request, 'tournaments/elimination_config_form.html', {'form': form, 'tournament': tournament})


@login_required
def edit_ladder_config(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    if request.user != tournament.created_by and not request.user.is_staff:
        messages.error(request, 'Tylko organizator może edytować konfigurację tego turnieju.')
        return redirect('tournaments:manage')

    if tournament.tournament_type != 'LDR':
        messages.error(request, 'Konfiguracja drabinki dostępna tylko dla turniejów typu Drabinka.')
        return redirect('tournaments:manage')

    config = getattr(tournament, 'ladder_config', None)

    if request.method == 'POST':
        form = LadderConfigForm(request.POST, instance=config)
        if form.is_valid():
            lc = form.save(commit=False)
            lc.tournament = tournament
            lc.save()
            messages.success(request, 'Konfiguracja drabinki została zapisana.')
            return redirect('tournaments:manage')
        else:
            messages.error(request, 'W formularzu wystąpiły błędy. Popraw i spróbuj ponownie.')
    else:
        form = LadderConfigForm(instance=config)

    return render(request, 'tournaments/ladder_config_form.html', {'form': form, 'tournament': tournament})


@login_required
def edit_americano_config(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    if request.user != tournament.created_by and not request.user.is_staff:
        messages.error(request, 'Tylko organizator może edytować konfigurację tego turnieju.')
        return redirect('tournaments:manage')

    if tournament.tournament_type != 'AMR':
        messages.error(request, 'Ta konfiguracja jest dostępna tylko dla turniejów typu Americano.')
        return redirect('tournaments:manage')

    config, _ = AmericanoConfig.objects.get_or_create(tournament=tournament)

    if request.method == 'POST':
        form = AmericanoConfigForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'Konfiguracja Americano została zapisana.')
            return redirect('tournaments:manage')
        else:
            messages.error(request, 'W formularzu wystąpiły błędy. Popraw i spróbuj ponownie.')
    else:
        form = AmericanoConfigForm(instance=config)

    return render(request, 'tournaments/americano_config_form.html', {'form': form, 'tournament': tournament})


@login_required
def edit_swiss_config(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    if request.user != tournament.created_by and not request.user.is_staff:
        messages.error(request, 'Tylko organizator może edytować konfigurację tego turnieju.')
        return redirect('tournaments:manage')

    if tournament.tournament_type != 'SWS':
        messages.error(request, 'Ta konfiguracja jest dostępna tylko dla turniejów w Systemie Szwajcarskim.')
        return redirect('tournaments:manage')

    config, _ = SwissSystemConfig.objects.get_or_create(tournament=tournament)

    if request.method == 'POST':
        form = SwissSystemConfigForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'Konfiguracja Systemu Szwajcarskiego została zapisana.')
            return redirect('tournaments:manage')
        else:
            messages.error(request, 'W formularzu wystąpiły błędy. Popraw i spróbuj ponownie.')
    else:
        form = SwissSystemConfigForm(instance=config)

    return render(request, 'tournaments/swiss_config_form.html', {'form': form, 'tournament': tournament})


@login_required
def list_participants(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    if request.user != tournament.created_by and not request.user.is_staff:
        messages.error(request, 'Brak uprawnień do zarządzania uczestnikami tego turnieju.')
        return redirect('tournaments:manage')

    t_any = cast(Any, tournament)
    participants = t_any.participants.all()
    participants = participants.order_by('seed_number', 'display_name')
    pending_requests = t_any.participants.filter(status='PEN')
    return render(request, 'tournaments/participants_list.html', {
        'tournament': tournament,
        'participants': participants,
        'pending_requests': pending_requests,
    })


@login_required
def request_join(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    user = request.user

    if user == tournament.created_by:
        messages.error(request, 'Nie możesz dołączyć do własnego turnieju w ten sposób.')
        return redirect('tournaments:manage')

    if Participant.objects.filter(tournament=tournament, user=user).exists():
        messages.warning(request, 'Już wysłałeś prośbę lub jesteś uczestnikiem tego turnieju.')
        return redirect('tournaments:manage')

    # --- POPRAWKA: Użyj pełnej nazwy użytkownika jako domyślnej ---
    display_name = user.get_full_name() or user.username

    Participant.objects.create(
        tournament=tournament,
        user=user,
        display_name=display_name,
        status=Participant.PARTICIPANT_STATUSES[0][0]
    )

    messages.success(request, f'Wysłano prośbę o dołączenie do turnieju "{tournament.name}". Oczekuje na zatwierdzenie.')

    organizer = tournament.created_by
    notification_message = f'Użytkownik {display_name} poprosił o dołączenie do turnieju "{tournament.name}".'
    notify_user(organizer, notification_message, 'info')

    return redirect('tournaments:manage')


@login_required
def approve_participant(request, pk, participant_pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    if request.user != tournament.created_by and not request.user.is_staff:
        messages.error(request, 'Brak uprawnień.')
        return redirect('tournaments:manage')

    participant = get_object_or_404(Participant, pk=participant_pk, tournament=tournament)
    cfg = tournament.config
    t_any = cast(Any, tournament)
    if cfg and t_any.participants.filter(status__in=['REG','ACT']).count() >= cfg.max_participants:
        messages.error(request, 'Nie można zatwierdzić — osiągnięto limit uczestników.')
        return redirect('tournaments:list_participants', pk=tournament.pk)

    participant.status = Participant.PARTICIPANT_STATUSES[1][0]
    participant.save()
    messages.success(request, 'Uczestnik zatwierdzony.')
    return redirect('tournaments:list_participants', pk=tournament.pk)


@login_required
def reject_participant(request, pk, participant_pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    if request.user != tournament.created_by and not request.user.is_staff:
        messages.error(request, 'Brak uprawnień.')
        return redirect('tournaments:manage')

    participant = get_object_or_404(Participant, pk=participant_pk, tournament=tournament)
    participant.status = Participant.PARTICIPANT_STATUSES[4][0]
    participant.save()
    messages.success(request, 'Prośba odrzucona.')
    return redirect('tournaments:list_participants', pk=tournament.pk)


@login_required
def register_participant(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    if tournament.status != 'REG' and request.user != tournament.created_by:
        messages.error(request, 'Rejestracja jest zamknięta.')
        return redirect('tournaments:manage')

    cfg = getattr(tournament, 'round_robin_config', None) or getattr(tournament, 'elimination_config', None)
    t_any = cast(Any, tournament)
    if cfg and t_any.participants.count() >= cfg.max_participants:
        messages.error(request, 'Osiągnięto limit uczestników dla tego turnieju.')
        return redirect('tournaments:manage')

    if request.method == 'POST':
        form = ParticipantForm(request.POST, tournament=tournament)
        if form.is_valid():
            p = form.save(commit=False)
            p.tournament = tournament
            if not p.user:
                p.user = request.user

            # Dla debla: obsłuż partnera i auto-nazwę
            if tournament.match_format == 'DBL':
                partner_id = request.POST.get('partner_user_id')
                if partner_id:
                    try:
                        partner_user = User.objects.get(pk=partner_id)
                        player_name = p.user.get_full_name() or p.user.username
                        partner_name = partner_user.get_full_name() or partner_user.username
                        p.display_name = f"{player_name} / {partner_name}"
                    except User.DoesNotExist:
                        pass

            p.save()

            # Zapisz partnera jako TeamMember
            if tournament.match_format == 'DBL':
                partner_id = request.POST.get('partner_user_id')
                if partner_id:
                    try:
                        partner_user = User.objects.get(pk=partner_id)
                        TeamMember.objects.update_or_create(
                            participant=p,
                            defaults={'user': partner_user}
                        )
                    except User.DoesNotExist:
                        pass

            messages.success(request, 'Zgłoszenie zapisane.')
            return redirect('tournaments:list_participants', pk=tournament.pk)
        else:
            messages.error(request, 'Błąd formularza. Sprawdź dane.')
    else:
        initial = {'user': request.user.pk, 'display_name': request.user.get_full_name() or request.user.username}
        form = ParticipantForm(initial=initial, tournament=tournament)

    is_doubles = tournament.match_format == 'DBL'
    all_users = User.objects.filter(is_superuser=False).order_by('first_name', 'last_name')
    return render(request, 'tournaments/participant_form.html', {
        'form': form, 'tournament': tournament, 'is_doubles': is_doubles, 'all_users': all_users
    })


@login_required
def edit_participant(request, pk, participant_pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    participant = get_object_or_404(Participant, pk=participant_pk, tournament=tournament)
    if request.user != tournament.created_by and request.user != participant.user:
        messages.error(request, 'Brak uprawnień do edycji tego zgłoszenia.')
        return redirect('tournaments:manage')

    if request.method == 'POST':
        form = ParticipantForm(request.POST, instance=participant, tournament=tournament)
        if form.is_valid():
            p = form.save(commit=False)

            # Dla debla: obsłuż zmianę partnera i odśwież display_name
            if tournament.match_format == 'DBL':
                partner_id = request.POST.get('partner_user_id')
                if partner_id:
                    try:
                        partner_user = User.objects.get(pk=partner_id)
                        player_name = p.user.get_full_name() or p.user.username if p.user else p.display_name
                        partner_name = partner_user.get_full_name() or partner_user.username
                        p.display_name = f"{player_name} / {partner_name}"
                        TeamMember.objects.update_or_create(
                            participant=p,
                            defaults={'user': partner_user}
                        )
                    except User.DoesNotExist:
                        pass
                else:
                    # Usunięcie partnera — wyczyść TeamMember i odśwież nazwę
                    TeamMember.objects.filter(participant=p).delete()
                    if p.user:
                        p.display_name = p.user.get_full_name() or p.user.username

            p.save()
            messages.success(request, 'Zgłoszenie zostało zaktualizowane.')
            return redirect('tournaments:list_participants', pk=tournament.pk)
        else:
            messages.error(request, 'Błąd formularza. Sprawdź dane.')
    else:
        form = ParticipantForm(instance=participant, tournament=tournament)

    is_doubles = tournament.match_format == 'DBL'
    all_users = User.objects.filter(is_superuser=False).order_by('first_name', 'last_name')
    current_partner = participant.members.select_related('user').first() if is_doubles else None
    return render(request, 'tournaments/participant_form.html', {
        'form': form, 'tournament': tournament, 'participant': participant,
        'is_doubles': is_doubles, 'all_users': all_users, 'current_partner': current_partner,
    })


@login_required
def add_team_member(request, pk, participant_pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    participant = get_object_or_404(Participant, pk=participant_pk, tournament=tournament)
    if request.user != tournament.created_by and request.user != participant.user:
        messages.error(request, 'Brak uprawnień.')
        return redirect('tournaments:manage')

    if tournament.match_format != 'DBL':
        messages.error(request, 'Zarządzanie członkami zespołu dotyczy tylko turniejów deblowych.')
        return redirect('tournaments:manage')

    # --- POPRAWKA: Znajdź istniejącego członka zespołu, aby go edytować, a nie dodawać nowego ---
    try:
        team_member_instance = TeamMember.objects.get(participant=participant)
    except TeamMember.DoesNotExist:
        team_member_instance = None

    if request.method == 'POST':
        form = TeamMemberForm(request.POST, instance=team_member_instance, participant=participant)
        if form.is_valid():
            m = form.save(commit=False)
            m.participant = participant
            m.save()
            # Zmiana komunikatu w zależności od tego, czy dodano nowego, czy zaktualizowano istniejącego członka
            message = 'Członek zespołu został zaktualizowany.' if team_member_instance else 'Członek zespołu został dodany.'
            messages.success(request, message)
            return redirect('tournaments:list_participants', pk=tournament.pk)
        else:
            messages.error(request, 'Błąd formularza.')
    else:
        form = TeamMemberForm(instance=team_member_instance, participant=participant)

    return render(request, 'tournaments/teammember_form.html', {'form': form, 'tournament': tournament, 'participant': participant})


@login_required
def remove_team_member(request, pk, participant_pk, member_pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    participant = get_object_or_404(Participant, pk=participant_pk, tournament=tournament)
    member = get_object_or_404(TeamMember, pk=member_pk, participant=participant)
    if request.user != tournament.created_by and request.user != participant.user:
        messages.error(request, 'Brak uprawnień.')
        return redirect('tournaments:manage')

    member.delete()
    messages.success(request, 'Członek zespołu usunięty.')
    return redirect('tournaments:list_participants', pk=tournament.pk)


@login_required
@require_POST
def remove_participant(request, pk, participant_pk):
    """Allow organizer (or staff) to remove a participant from the tournament."""
    tournament = get_object_or_404(Tournament, pk=pk)
    participant = get_object_or_404(Participant, pk=participant_pk, tournament=tournament)
    if request.user != tournament.created_by and not request.user.is_staff:
        messages.error(request, 'Brak uprawnień do usunięcia uczestnika.')
        return redirect('tournaments:manage')

    participant.delete()
    messages.success(request, 'Uczestnik został usunięty z turnieju.')
    return redirect('tournaments:list_participants', pk=tournament.pk)


@login_required
@require_POST
def revert_to_draft(request, pk):
    """
    Pozwala organizatorowi na zmianę statusu turnieju z REG na DRF.
    """
    tournament = get_object_or_404(Tournament, pk=pk)

    if request.user != tournament.created_by and not request.user.is_staff:
        messages.error(request, 'Brak uprawnień do zmiany statusu tego turnieju.')
        return redirect('tournaments:manage')

    if tournament.status in ['REG', 'SCH']:
        tournament.status = Tournament.Status.DRAFT.value
        tournament.save()
        messages.success(request, f'Status turnieju "{tournament.name}" został zmieniony na Szkic (Draft). Rejestracja została zamknięta.')
    else:
        messages.warning(request, f'Nie można zmienić statusu z "{tournament.get_status_display()}" na Szkic. Akcja jest dostępna tylko dla statusu Zarejestrowany (REG).')

    return redirect('tournaments:manage')


@login_required
@require_POST
def open_registration(request, pk):
    """
    Pozwala organizatorowi na zmianę statusu turnieju z DRF (Szkic) na REG (Rejestracja).
    """
    tournament = get_object_or_404(Tournament, pk=pk)

    if request.user != tournament.created_by and not request.user.is_staff:
        messages.error(request, 'Brak uprawnień do zmiany statusu tego turnieju.')
        return redirect('tournaments:manage')

    if tournament.is_draft:
        tournament.status = Tournament.Status.REGISTRATION.value
        tournament.save()
        messages.success(request, f'Otwarto rejestrację dla turnieju "{tournament.name}".')
    else:
        messages.warning(request, f'Nie można otworzyć rejestracji. Turniej jest w statusie "{tournament.get_status_display()}".')

    return redirect('tournaments:manage')


@login_required
@require_POST
def close_registration(request, pk):
    """
    Pozwala organizatorowi na zmianę statusu turnieju z REG (Rejestracja) na SCH (Zaplanowany).
    """
    tournament = get_object_or_404(Tournament, pk=pk)

    if request.user != tournament.created_by and not request.user.is_staff:
        messages.error(request, 'Brak uprawnień do zmiany statusu tego turnieju.')
        return redirect('tournaments:manage')

    if tournament.is_open_for_registration:
        tournament.status = Tournament.Status.SCHEDULED.value
        tournament.save()

        participants_to_update = Participant.objects.filter(tournament=tournament, status=Participant.PARTICIPANT_STATUSES[1][0])
        updated_count = participants_to_update.update(status=Participant.PARTICIPANT_STATUSES[2][0])

        if tournament.tournament_type == Tournament.TournamentType.LADDER:
            config = tournament.ladder_config
            if config:
                participants = list(tournament.participants.filter(status=Participant.PARTICIPANT_STATUSES[2][0]))

                if config.initial_seeding == 'RANDOM':
                    random.shuffle(participants)
                    for i, p in enumerate(participants, 1):
                        p.seed_number = i
                        p.save(update_fields=['seed_number'])
                    messages.info(request, "Ustawiono losową kolejność początkową w drabince.")
                
                elif config.initial_seeding == 'SEEDING':
                    participants.sort(key=lambda p: (p.seed_number is None, p.seed_number, random.random()))
                    for i, p in enumerate(participants, 1):
                        p.seed_number = i
                        p.save(update_fields=['seed_number'])
                    messages.info(request, "Ustawiono kolejność w drabince na podstawie numerów rozstawienia (seed).")

        messages.success(request, f'Zamknięto rejestrację dla turnieju "{tournament.name}". Status zmieniono na "Zaplanowany".')
        if updated_count > 0:
            messages.info(request, f'Zmieniono status {updated_count} uczestników na "Aktywny w rozgrywkach".')
    else:
        messages.warning(request, f'Nie można zamknąć rejestracji. Turniej jest w statusie "{tournament.get_status_display()}".')

    return redirect('tournaments:manage')


@login_required
@require_POST
def start_tournament(request, pk):
    """
    Pozwala organizatorowi na zmianę statusu turnieju z SCH (Zaplanowany) na ACT (Rozpoczęty).
    """
    tournament = get_object_or_404(Tournament, pk=pk)

    if request.user != tournament.created_by and not request.user.is_staff:
        messages.error(request, 'Brak uprawnień do rozpoczęcia tego turnieju.')
        return redirect('tournaments:manage')

    if tournament.status == Tournament.Status.SCHEDULED:
        if tournament.tournament_type != Tournament.TournamentType.LADDER and not tournament.matches.exists():
            messages.error(request, 'Nie można rozpocząć turnieju bez wygenerowanych meczów.')
            return redirect('tournaments:manage')

        tournament.status = Tournament.Status.ACTIVE.value
        tournament.start_date = timezone.now()
        tournament.save()
        messages.success(request, f'Turniej "{tournament.name}" został oficjalnie rozpoczęty.')
    else:
        messages.warning(request, f'Nie można rozpocząć turnieju, który jest w statusie "{tournament.get_status_display()}".')

    return redirect('tournaments:manage')


def determine_winner(tournament):
    """
    Określa zwycięzcę turnieju na podstawie jego typu i wyników.
    """
    if tournament.tournament_type == Tournament.TournamentType.SINGLE_ELIMINATION:
        # Zwycięzcą jest zwycięzca ostatniego meczu (finału)
        final_match = tournament.matches.order_by('-round_number', '-match_index').first()
        if final_match and final_match.winner:
            return final_match.winner

    elif tournament.tournament_type == Tournament.TournamentType.ROUND_ROBIN:
        # Zwycięzcą jest gracz na pierwszym miejscu w tabeli
        participants = tournament.participants.filter(status__in=['ACT', 'REG'])
        standings = {p.id: {'participant': p, 'points': 0, 'sets_diff': 0, 'games_diff': 0} for p in participants}
        
        # Uproszczone obliczanie punktów - w rzeczywistości powinno być to samo co w widoku details
        for match in tournament.matches.filter(status=TournamentsMatch.Status.COMPLETED):
            if match.winner_id in standings:
                standings[match.winner_id]['points'] += 1 # Uproszczone

        if standings:
            standings_list = sorted(standings.values(), key=lambda x: x['points'], reverse=True)
            if standings_list:
                return standings_list[0]['participant']

    elif tournament.tournament_type == Tournament.TournamentType.LADDER:
        # Zwycięzcą jest gracz na szczycie drabinki (najniższy seed_number)
        winner = tournament.participants.filter(
            status__in=[Participant.PARTICIPANT_STATUSES[1][0], Participant.PARTICIPANT_STATUSES[2][0]]
        ).order_by('seed_number').first()
        return winner

    elif tournament.tournament_type == Tournament.TournamentType.AMERICANO.value:
        # Zwycięzcą jest gracz na pierwszym miejscu w tabeli punktowej
        standings_list = calculate_americano_standings(tournament)
        if standings_list:
            # Lista jest już posortowana, więc pierwszy element to zwycięzca
            return standings_list[0]['participant']

    elif tournament.tournament_type == Tournament.TournamentType.SWISS:
        standings = get_participant_standings_swiss(tournament)
        # Sortowanie po wygranych (malejąco), przegranych (rosnąco)
        sorted_standings = sorted(standings.values(), key=lambda x: (x['wins'], -x['losses']), reverse=True)
        if sorted_standings:
            return sorted_standings[0]['participant']

    elif tournament.tournament_type == Tournament.TournamentType.DOUBLE_ELIMINATION.value:
        # Zwycięzcą jest zwycięzca Wielkiego Finału (runda 99)
        # Jeśli go nie ma, szukamy ostatniego zakończonego meczu (fallback)
        grand_final = tournament.matches.filter(round_number=99).first()
        if grand_final and grand_final.winner:
            return grand_final.winner
        
        # Fallback: ostatni zakończony mecz
        final_match = tournament.matches.filter(
            status=TournamentsMatch.Status.COMPLETED.value
        ).order_by('-round_number', '-match_index').first()
        
        if final_match and final_match.winner:
            return final_match.winner

    return None


@login_required
@require_POST
def finish_tournament(request, pk):
    """
    Pozwala organizatorowi na ręczne zakończenie turnieju.
    """
    tournament = get_object_or_404(Tournament, pk=pk)

    if request.user != tournament.created_by and not request.user.is_staff:
        messages.error(request, 'Tylko organizator może zakończyć ten turniej.')
        return redirect('tournaments:manage')

    if tournament.status == Tournament.Status.ACTIVE:
        tournament.status = Tournament.Status.FINISHED.value
        tournament.end_date = timezone.now()
        
        # Ustal i zapisz zwycięzcę
        winner = determine_winner(tournament)
        if winner:
            tournament.winner = winner

        tournament.save()
        messages.success(request, f'Turniej "{tournament.name}" został zakończony.')
    else:
        messages.warning(request, f'Nie można zakończyć turnieju, który jest w statusie "{tournament.get_status_display()}".')

    return redirect('tournaments:manage')


def get_tournament_config(tournament):
    """Pobiera konfigurację dla danego typu turnieju."""
    if tournament.tournament_type == 'RND':
        return getattr(tournament, 'round_robin_config', None)
    elif tournament.tournament_type in ['SGL', 'DBE']:
        return getattr(tournament, 'elimination_config', None)
    elif tournament.tournament_type == 'LDR':
        return getattr(tournament, 'ladder_config', None)
    elif tournament.tournament_type == 'AMR':
        return getattr(tournament, 'americano_config', None)
    elif tournament.tournament_type == 'SWS':
        return getattr(tournament, 'swiss_system_config', None)
    return None


PREDEFINED_SEEDING_ORDERS = {
    2: [1, 2],
    4: [1, 4, 3, 2],
    8: [1, 8, 5, 4, 3, 6, 7, 2],
    16: [1, 16, 9, 8, 5, 12, 13, 4, 3, 14, 11, 6, 7, 10, 15, 2],
    32: [1, 32, 17, 16, 9, 24, 25, 8, 5, 28, 21, 12, 13, 20, 29, 4, 3, 30, 19, 14, 11, 22, 27, 6, 7, 26, 23, 10, 15, 18, 31, 2]
}


def _generate_seed_to_slot_map(bracket_size):
    """
    Generuje mapowanie numeru rozstawienia (1-indeksowany) na indeks slotu w drabince (0-indeksowany)
    zgodnie ze standardowym schematem rozstawiania w profesjonalnym tenisie.
    """
    if bracket_size == 0:
        return {}
    if bracket_size == 1:
        return {1: 0}

    # Krok 1: Spróbuj użyć predefiniowanego schematu rozstawienia
    if bracket_size in PREDEFINED_SEEDING_ORDERS:
        slots = PREDEFINED_SEEDING_ORDERS[bracket_size]
    else:
        # Krok 2: Jeśli schemat nie jest zdefiniowany, oblicz go dynamicznie (fallback)
        # Inicjalizacja: Zaczynamy od drabinki dla 2 graczy
        slots = [1, 2]
        
        # Iteracyjnie podwajamy rozmiar drabinki, aż osiągniemy docelowy rozmiar.
        while len(slots) < bracket_size:
            new_slots = []
            # Dla każdego numeru rozstawienia w obecnej drabince, dodajemy go
            # oraz jego "lustrzane" odbicie w nowej, większej drabince.
            for seed in slots:
                new_slots.append(seed)
                new_slots.append(len(slots) * 2 + 1 - seed)
            slots = new_slots
    
    # Tworzymy słownik mapujący numer rozstawienia na pozycję w drabince
    # Przykład dla 8: [1, 8, 5, 4, 3, 6, 7, 2]
    # Przykład dla 16: [1, 16, 9, 8, 5, 12, 13, 4, 3, 14, 11, 6, 7, 10, 15, 2]
    return {seed: index for index, seed in enumerate(slots)}


def generate_round_robin_matches_initial(tournament, participants_qs):
    """
    Generuje wszystkie mecze dla turnieju "każdy z każdym" (Round Robin)
    i zapisuje je w bazie danych.
    """
    from itertools import combinations

    if participants_qs.count() < 2:
        return 0, "Za mało uczestników (wymagane co najmniej 2), aby wygenerować mecze."

    TournamentsMatch.objects.filter(tournament=tournament).delete()

    match_pairs = combinations(participants_qs, 2)

    matches_to_create = [
        TournamentsMatch(
            tournament=tournament, 
            participant1=p1, 
            participant2=p2, 
            round_number=1, 
            match_index=i,
            status=TournamentsMatch.Status.WAITING.value)
        for i, (p1, p2) in enumerate(match_pairs, 1)
    ]

    created_matches = TournamentsMatch.objects.bulk_create(matches_to_create)
    return len(created_matches), f"Wygenerowano {len(created_matches)} meczów."


def generate_elimination_matches_initial(tournament, participants_qs, config):
    """
    Generuje mecze pierwszej rundy dla turnieju pucharowego (Single Elimination),
    uwzględniając rozstawienie (seeding) i wolne losy (byes).
    """
    num_participants = participants_qs.count()
    if num_participants < 2:
        return 0, "Za mało uczestników (wymagane co najmniej 2), aby wygenerować drabinkę."

    TournamentsMatch.objects.filter(tournament=tournament).delete()

    # Oblicz rozmiar drabinki (najbliższa potęga dwójki) i liczbę wolnych losów
    bracket_size = 2**math.ceil(math.log2(num_participants))
    num_byes = bracket_size - num_participants

    # Sprawdź, czy używać rozstawienia
    use_seeding = (config.initial_seeding == 'SEEDING') and any(p.seed_number is not None for p in participants_qs)

    # Ta lista będzie przechowywać obiekty Participant lub None (dla wolnych losów) w odpowiednich slotach drabinki
    final_bracket_slots = [None] * bracket_size

    if use_seeding:
        # Dzielimy uczestników na rozstawionych i nierozstawionych
        seeded_participants = {p.seed_number: p for p in participants_qs if p.seed_number is not None}
        unseeded_participants = [p for p in participants_qs if p.seed_number is None]
        random.shuffle(unseeded_participants) # Mieszamy nierozstawionych graczy

        # Wygeneruj mapowanie numeru rozstawienia na slot w drabince
        seed_to_slot_map = _generate_seed_to_slot_map(bracket_size)
        
        # Krok 1: Umieść rozstawionych graczy w ich dedykowanych slotach
        for seed_num, participant in seeded_participants.items():
            slot_idx = seed_to_slot_map.get(seed_num)
            if slot_idx is not None and slot_idx < bracket_size:
                final_bracket_slots[slot_idx] = participant

        # Krok 2: Wypełnij pozostałe wolne sloty nierozstawionymi graczami
        # Najpierw znajdujemy wszystkie puste sloty
        empty_slots_indices = [i for i, slot in enumerate(final_bracket_slots) if slot is None]
        
        # Następnie wypełniamy je nierozstawionymi graczami
        for i, slot_idx in enumerate(empty_slots_indices):
            if i < len(unseeded_participants):
                final_bracket_slots[slot_idx] = unseeded_participants[i]
            else:
                # Jeśli zabraknie nierozstawionych graczy, reszta to wolne losy (None)
                break
            
    else: # Losowe rozmieszczenie
        # Jeśli rozstawienie jest wyłączone, wszyscy są traktowani jako nierozstawieni
        all_participants = list(participants_qs)
        random.shuffle(all_participants)
        
        # Wypełnij sloty uczestnikami, a resztę wolnymi losami
        temp_slots = all_participants + [None] * num_byes
        
        # Mieszanie dystrybuuje uczestników i wolne losy całkowicie losowo
        random.shuffle(temp_slots)
        final_bracket_slots = temp_slots

    matches_to_create = []
    match_index = 1

    # Twórz mecze pierwszej rundy, parując sąsiednie sloty
    for i in range(0, bracket_size, 2):
        p1_slot = final_bracket_slots[i]
        p2_slot = final_bracket_slots[i+1]

        if p1_slot is None:
            # p2_slot otrzymuje wolny los (bye)
            matches_to_create.append(TournamentsMatch(
                tournament=tournament, participant1=p2_slot, participant2=None,
                round_number=1, match_index=match_index, status=TournamentsMatch.Status.COMPLETED.value, winner=p2_slot
            ))
        elif p2_slot is None:
            # p1_slot otrzymuje wolny los (bye)
            matches_to_create.append(TournamentsMatch(
                tournament=tournament, participant1=p1_slot, participant2=None,
                round_number=1, match_index=match_index, status=TournamentsMatch.Status.COMPLETED.value, winner=p1_slot
            ))
        else:
            # Obaj gracze są obecni, utwórz standardowy mecz
            matches_to_create.append(TournamentsMatch(
                tournament=tournament, participant1=p1_slot, participant2=p2_slot,
                round_number=1, match_index=match_index, status=TournamentsMatch.Status.WAITING.value
            ))
        match_index += 1

    created_matches = TournamentsMatch.objects.bulk_create(matches_to_create)
    return len(created_matches), f"Wygenerowano drabinkę dla {num_participants} uczestników ({len(matches_to_create)} meczów, {num_byes} wolnych losów)."


def generate_americano_matches(tournament, participants_qs, config):
    """
    Generuje mecze dla turnieju Americano na podstawie liczby graczy i rund.
    Używa algorytmu "circle method" do rotacji graczy.
    """
    num_participants = participants_qs.count()
    if num_participants < 4 or num_participants % 4 != 0:
        return 0, f"Nieprawidłowa liczba uczestników ({num_participants}). Musi być to wielokrotność 4 i co najmniej 4 graczy."

    TournamentsMatch.objects.filter(tournament=tournament).delete()

    num_courts = num_participants // 4
    matches_to_create = []

    if config.scheduling_type == 'DYNAMIC':
        # Tryb Mexicano: generujemy tylko jedną rundę na podstawie rankingu (seed)
        participants = list(participants_qs.order_by('seed_number'))
        num_rounds = 1 # Tylko jedna runda
        message = f"Wygenerowano 1. rundę ({len(participants) // 4} meczów) dla trybu Mexicano na podstawie rankingu."
        
        # Dzielimy graczy na mecze
        for i in range(num_courts):
            match_index = i + 1
            # Gracze są brani po kolei z posortowanej listy
            p1, p2, p3, p4 = participants[i*4 : (i+1)*4]
            # Tworzymy mecz: (1,4) vs (2,3) - standardowe parowanie w Mexicano
            matches_to_create.append(
                TournamentsMatch(
                    tournament=tournament,
                    participant1=p1, participant2=p4, # Team A
                    participant3=p2, participant4=p3, # Team B
                    round_number=1,
                    match_index=match_index,
                    status=TournamentsMatch.Status.WAITING.value
                )
            )
    else:
        # Tryb Americano (STATIC): generujemy wszystkie rundy losowo
        participants = list(participants_qs)
        random.shuffle(participants)
        num_rounds = config.number_of_rounds
        message = f"Wygenerowano losowo {num_rounds} rund ({num_rounds * num_courts} meczów) dla trybu Americano."

        # Algorytm rotacji: jeden gracz jest stały, reszta się obraca
        p_last = participants[-1]
        p_others = participants[:-1]

        for r in range(num_rounds):
            round_number = r + 1
            current_round_players = p_others + [p_last]

            for i in range(num_courts):
                match_index = i + 1
                p1 = current_round_players[i]
                p2 = current_round_players[i + num_courts]
                p3 = current_round_players[i + 2 * num_courts]
                p4 = current_round_players[i + 3 * num_courts]

                matches_to_create.append(
                    TournamentsMatch(
                        tournament=tournament,
                        participant1=p1, participant2=p4, # Team A
                        participant3=p2, participant4=p3, # Team B
                        round_number=round_number,
                        match_index=match_index,
                        status=TournamentsMatch.Status.WAITING.value
                    )
                )
            # Rotacja graczy (bez ostatniego) na następną rundę
            p_others = [p_others[-1]] + p_others[:-1]

    created_matches = TournamentsMatch.objects.bulk_create(matches_to_create)
    return len(created_matches), message


def generate_next_mexicano_round(tournament, config, standings_list):
    """
    Generuje następną rundę dla turnieju w trybie Mexicano na podstawie aktualnej tabeli.
    """
    current_max_round = tournament.matches.aggregate(max_round=Max('round_number')).get('max_round') or 0
    next_round_number = current_max_round + 1

    if next_round_number > config.number_of_rounds:
        return 0, "Osiągnięto maksymalną liczbę rund. Turniej można zakończyć."

    participants = [s['participant'] for s in standings_list]
    num_participants = len(participants)
    num_courts = num_participants // 4
    matches_to_create = []

    for i in range(num_courts):
        match_index = i + 1
        # Gracze są brani po kolei z posortowanej listy
        p1, p2, p3, p4 = participants[i*4 : (i+1)*4]
        # Tworzymy mecz: (1,4) vs (2,3) - standardowe parowanie w Mexicano
        matches_to_create.append(
            TournamentsMatch(
                tournament=tournament,
                participant1=p1, participant2=p4, # Team A
                participant3=p2, participant4=p3, # Team B
                round_number=next_round_number,
                match_index=match_index,
                status=TournamentsMatch.Status.WAITING.value
            )
        )
    
    created_matches = TournamentsMatch.objects.bulk_create(matches_to_create)
    message = f"Automatycznie wygenerowano {len(created_matches)} meczów dla rundy {next_round_number}."
    return len(created_matches), message


def generate_next_elimination_round(tournament, completed_round_number):
    """
    Generuje mecze dla następnej rundy na podstawie zwycięzców z rundy zakończonej.
    """
    previous_matches = TournamentsMatch.objects.filter(
        tournament=tournament,
        round_number=completed_round_number,
        status=TournamentsMatch.Status.COMPLETED.value
    ).order_by('match_index')

    winners = [match.winner for match in previous_matches if match.winner]

    if len(winners) <= 1:
        # Usunięto automatyczne kończenie turnieju. Organizator musi zakończyć go ręcznie.
        # tournament.status = Tournament.Status.FINISHED.value
        # tournament.save()
        winner_name = winners[0].display_name if winners else 'nie wyłoniono'
        return 0, f"Wyłoniono zwycięzcę turnieju: {winner_name}. Możesz teraz ręcznie zakończyć turniej."

    # Sprawdź, czy to runda generująca finał i czy jest włączony mecz o 3. miejsce
    config = getattr(tournament, 'elimination_config', None)
    if len(winners) == 2 and config and config.third_place_match:
        # Przegrani z półfinałów grają o 3. miejsce
        semi_final_losers = []
        for match in previous_matches:
            if match.winner:
                # Poprawiona logika znajdowania przegranego
                loser = None
                if match.participant1 and match.participant2: # Upewnij się, że obaj uczestnicy istnieją
                    if match.winner.id == match.participant1.id:
                        loser = match.participant2
                    else:
                        loser = match.participant1
                if loser: # Dodaj do listy tylko jeśli przegrany został jednoznacznie zidentyfikowany
                    semi_final_losers.append(loser)
        
        if len(semi_final_losers) == 2:
            # Utwórz mecz o 3. miejsce z numerem rundy 0 dla łatwej identyfikacji
            TournamentsMatch.objects.create(
                tournament=tournament,
                participant1=semi_final_losers[0],
                participant2=semi_final_losers[1],
                round_number=0, # Specjalny numer rundy dla meczu o 3. miejsce
                match_index=1,
                status=TournamentsMatch.Status.WAITING.value
            )

    next_round_number = completed_round_number + 1
    matches_to_create = []
    match_index = 1

    for i in range(0, len(winners), 2):
        p1 = winners[i]
        p2 = winners[i+1] if (i+1) < len(winners) else None
        
        matches_to_create.append(TournamentsMatch(
            tournament=tournament,
            participant1=p1,
            participant2=p2,
            round_number=next_round_number,
            match_index=match_index,
            status=TournamentsMatch.Status.WAITING.value
        ))
        match_index += 1

    created_matches = TournamentsMatch.objects.bulk_create(matches_to_create)
    return len(created_matches), f"Automatycznie wygenerowano {len(created_matches)} meczów dla rundy {next_round_number}."


def advance_double_elimination(tournament, match):
    """
    Obsługuje logikę awansu w turnieju podwójnej eliminacji.
    Tworzy lub aktualizuje mecze w drabince wygranych (WB), przegranych (LB) oraz Wielkim Finale.
    """
    if not match.winner:
        return

    # Ustalenie parametrów drabinki
    # Zakładamy, że runda 1 to start WB.
    # Drabinka przegranych (LB) ma specyficzną numerację rund.
    
    # Sprawdźmy, czy mecz jest w drabince wygranych (WB) czy przegranych (LB)
    # W typowej implementacji DB w bazie:
    # WB Rundy: 1, 2, 3...
    # LB Rundy: Często numeruje się je osobno, ale tutaj musimy je rozróżnić.
    # Przyjmijmy konwencję:
    # WB to rundy, gdzie match.round_number > 0 (standardowo).
    # Ale jak odróżnić LB?
    # W tym podejściu będziemy dynamicznie sprawdzać ścieżkę.
    # Dla uproszczenia w jednym modelu: 
    # Przyjmijmy, że 'round_number' jest globalny, ale musimy wiedzieć czy to WB czy LB.
    # W DB często stosuje się ujemne numery rund dla LB lub flagę. 
    # Ponieważ nie mamy pola 'bracket_type', użyjemy prostej heurystyki lub dodatkowego pola w modelu (którego nie mamy).
    # Zamiast tego, zaimplementujmy logikę opartą na "Loser drops to...".
    
    # --- UPROSZCZENIE DLA TEGO MODELU ---
    # Ponieważ nie mamy pola "bracket_type", musimy śledzić mecze po ich ID lub relacjach.
    # Jednak najprościej jest zdefiniować, że mecze tworzone przez "spadkowiczów" są w LB.
    # Aby to działało w obecnym modelu, musimy wiedzieć, czy aktualny mecz był w WB czy LB.
    # Możemy to wywnioskować: Jeśli mecz był w R1, to na pewno WB.
    # Jeśli nie, to trudniej.
    # ALE: W widoku details_double_elimination rozdzieliliśmy mecze na WB i LB w szablonie? 
    # W poprzednim kroku (szablon) użyliśmy jednej listy.
    # Zróbmy tak: Dodajmy pole `is_losers_bracket` do modelu TournamentsMatch w przyszłości.
    # TERAZ: Użyjemy konwencji logicznej.
    
    # Algorytm "Standard Double Elimination":
    # WB Round R -> Winner -> WB Round R+1
    # WB Round R -> Loser -> LB Round L (zależne od R)
    
    # LB Round L -> Winner -> LB Round L+1
    # LB Round L -> Loser -> Eliminated

    # Aby wiedzieć czy jesteśmy w WB czy LB bez dodatkowego pola:
    # Sprawdzamy historię meczu? Nie.
    # Zastosujmy "Hack": W Double Elimination, runda WB zawsze ma potęgę 2 meczów (np. 8, 4, 2, 1).
    # Rundy LB mają inną strukturę.
    # Jednak najbezpieczniej jest, jeśli `generate_double_elimination_matches_initial` oznaczy mecze.
    # Skoro nie możemy zmienić modelu teraz, załóżmy, że mecze są tworzone dynamicznie.
    
    # --- IMPLEMENTACJA ---
    # Będziemy przekazywać informację o typie drabinki w `match_index`? Nie, to ryzykowne.
    # Zaufajmy strukturze:
    # Jeśli mecz jest w WB, przegrany spada do LB.
    # Jeśli mecz jest w LB, przegrany odpada.
    
    # Jak rozpoznać WB vs LB?
    # WB R1 to Runda 1.
    # Każdy mecz, do którego trafia ZWYCIĘZCA z WB, jest w WB.
    # Każdy mecz, do którego trafia PRZEGRANY z WB, jest w LB.
    # Każdy mecz, do którego trafia ZWYCIĘZCA z LB, jest w LB (chyba że to finał LB -> Grand Final).
    
    # Potrzebujemy pomocniczej funkcji, która znajdzie docelowy mecz.
    pass 
    # (Pełna implementacja poniżej w bloku kodu, zastępując ten placeholder)

def get_or_create_match(tournament, round_num, match_idx):
    match, created = TournamentsMatch.objects.get_or_create(
        tournament=tournament,
        round_number=round_num,
        match_index=match_idx,
        defaults={'status': TournamentsMatch.Status.WAITING.value}
    )
    return match

def generate_double_elimination_matches_initial(tournament, participants_qs, config):
    """
    Generuje początkową drabinkę (WB Runda 1) dla Double Elimination.
    """
    # 1. Generujemy standardową drabinkę pucharową jako WB Runda 1
    count, msg = generate_elimination_matches_initial(tournament, participants_qs, config)
    
    # 2. Dla każdego meczu, który jest "Bye" (automatycznie zakończony), musimy od razu pchnąć zwycięzcę dalej.
    # W generate_elimination_matches_initial mecze z Bye mają status COMPLETED i ustawionego winnera.
    initial_matches = TournamentsMatch.objects.filter(
        tournament=tournament, 
        round_number=1, 
        status=TournamentsMatch.Status.COMPLETED.value
    )
    
    for match in initial_matches:
        # Symulujemy awans dla wolnych losów
        advance_double_elimination(tournament, match)
        
    return count, msg

def is_match_in_losers_bracket(tournament, match):
    """
    Pomocnicza funkcja heurystyczna do określenia, czy mecz jest w drabince przegranych.
    W DB:
    WB Rundy: 1, 2, 3... (gdzie liczba meczów to N/2, N/4...)
    LB Rundy: Mają specyficzne indeksy.
    
    Dla uproszczenia w tym systemie przyjmiemy konwencję indeksowania:
    WB mecze mają indeksy < 1000.
    LB mecze mają indeksy >= 1000.
    To pozwoli nam łatwo rozróżnić drabinki bez migracji bazy danych.
    """
    return match.match_index >= 1000

def get_wb_next_match_index(current_index):
    return math.ceil(current_index / 2)

def get_lb_drop_round(wb_round):
    # Formuła mapowania rundy WB na rundę LB, do której spada przegrany
    # WB 1 -> LB 1
    # WB 2 -> LB 2
    # WB 3 -> LB 4
    # WB 4 -> LB 6
    if wb_round == 1:
        return 1
    else:
        return (wb_round - 1) * 2


@login_required
@require_POST
def generate_matches(request, pk):
    """
    Widok-akcja do generowania meczów dla turnieju.
    """
    tournament = get_object_or_404(Tournament, pk=pk)

    if request.user != tournament.created_by and not request.user.is_staff:
        messages.error(request, 'Brak uprawnień do generowania meczów.')
        return redirect('tournaments:manage_matches', pk=tournament.pk)

    participants_qs = Participant.objects.filter(
        tournament=tournament,
        status__in=[Participant.PARTICIPANT_STATUSES[2][0], Participant.PARTICIPANT_STATUSES[1][0]]
    )

    count = 0
    message = "Nie zaimplementowano generowania dla tego typu turnieju."

    if tournament.tournament_type == Tournament.TournamentType.ROUND_ROBIN:
        count, message = generate_round_robin_matches_initial(tournament, participants_qs)
    elif tournament.tournament_type == Tournament.TournamentType.SINGLE_ELIMINATION:
        config = tournament.config
        if not config:
            messages.error(request, "Brak konfiguracji dla tego turnieju. Przejdź do ustawień, aby ją utworzyć.")
            return redirect('tournaments:manage_matches', pk=tournament.pk)
        
        count, message = generate_elimination_matches_initial(tournament, participants_qs, config)
    elif tournament.tournament_type == Tournament.TournamentType.DOUBLE_ELIMINATION:
        config = tournament.config
        if not config:
             # Fallback jeśli brak konfiguracji, chociaż create_tournament zapewnia jej istnienie
             config, _ = EliminationConfig.objects.get_or_create(tournament=tournament)
        count, message = generate_double_elimination_matches_initial(tournament, participants_qs, config)
    elif tournament.tournament_type == Tournament.TournamentType.AMERICANO:
        config = tournament.config
        if not config:
            messages.error(request, "Brak konfiguracji dla tego turnieju. Przejdź do ustawień, aby ją utworzyć.")
            return redirect('tournaments:manage_matches', pk=tournament.pk)
        
        count, message = generate_americano_matches(tournament, participants_qs, config)
    elif tournament.tournament_type == Tournament.TournamentType.SWISS:
        config = tournament.config
        if not config:
            messages.error(request, "Brak konfiguracji. Zapisz ustawienia przed generowaniem meczów.")
            return redirect('tournaments:manage_matches', pk=tournament.pk)
        
        # Jeśli nie ma meczów -> 1. runda
        if not tournament.matches.exists():
            count, message = generate_swiss_matches_initial(tournament, participants_qs, config)
        else:
            # Kolejna runda
            # Sprawdź czy poprzednia zakończona
            active_matches = tournament.matches.exclude(status=TournamentsMatch.Status.COMPLETED.value)
            if active_matches.exists():
                messages.error(request, "Nie można wygenerować kolejnej rundy, dopóki wszystkie mecze bieżącej rundy nie zostaną zakończone.")
                return redirect('tournaments:manage_matches', pk=tournament.pk)
            
            count, message = generate_next_swiss_round(tournament, config)

    if count > 0:
        messages.success(request, message)
    else:
        messages.warning(request, message)

    return redirect('tournaments:manage_matches', pk=tournament.pk)


@login_required
def manage_matches(request, pk):
    """Widok do wyświetlania i zarządzania meczami turnieju."""
    tournament = get_object_or_404(Tournament, pk=pk)

    if request.user != tournament.created_by and not request.user.is_staff:
        messages.error(request, 'Brak uprawnień do zarządzania meczami tego turnieju.')
        return redirect('tournaments:manage')

    # --- POPRAWKA: Wyklucz mecze techniczne (TBA vs TBA) ---
    matches = TournamentsMatch.objects.filter(tournament=tournament).filter(
        Q(participant1__isnull=False) | Q(participant2__isnull=False)
    ).order_by('round_number', 'match_index')

    participants_qs = Participant.objects.filter(
        tournament=tournament,
        status__in=[Participant.PARTICIPANT_STATUSES[1][0], Participant.PARTICIPANT_STATUSES[2][0]]
    ).order_by('seed_number', 'display_name')

    can_reset_ladder = False
    if tournament.tournament_type == 'LDR':
        from django.db.models import Max
        current_max_round = tournament.matches.aggregate(max_round=Max('round_number')).get('max_round')
        if current_max_round:
            # Przycisk resetu jest aktywny, jeśli w najwyższej rundzie istnieje jakikolwiek "prawdziwy" mecz
            # (czyli mecz z indeksem > 0, który nie jest meczem technicznym).
            can_reset_ladder = tournament.matches.filter(
                round_number=current_max_round, match_index__gt=0
            ).exists()

    context = {
        'tournament': tournament,
        'matches': matches,
        'participants_count': participants_qs.count(),
        'is_seeded': getattr(get_tournament_config(tournament), 'initial_seeding', 'RANDOM') == 'SEEDING',
        'can_reset_ladder': can_reset_ladder,
    }

    return render(request, 'tournaments/manage_matches.html', context)


@login_required
@require_POST
def create_challenge_match(request, pk):
    """
    Tworzy mecz na podstawie wyzwania w turnieju drabinkowym.
    """
    tournament = get_object_or_404(Tournament, pk=pk, tournament_type=Tournament.TournamentType.LADDER.value)

    challenger_id = request.POST.get('challenger_id')
    challenged_id = request.POST.get('challenged_id')

    if not challenger_id or not challenged_id:
        messages.error(request, "Nieprawidłowe żądanie wyzwania.")
        return redirect('tournaments:details_ladder', pk=tournament.pk)

    try:
        challenger = get_object_or_404(Participant, pk=challenger_id, tournament=tournament)
        challenged = get_object_or_404(Participant, pk=challenged_id, tournament=tournament)
    except Participant.DoesNotExist:
        messages.error(request, "Podani uczestnicy nie istnieją.")
        return redirect('tournaments:details_ladder', pk=tournament.pk)

    if request.user != challenger.user:
        messages.error(request, "Nie masz uprawnień do rzucenia tego wyzwania.")
        return redirect('tournaments:details_ladder', pk=tournament.pk)

    active_statuses = [TournamentsMatch.Status.WAITING.value, TournamentsMatch.Status.SCHEDULED.value, TournamentsMatch.Status.IN_PROGRESS.value]

    if TournamentsMatch.objects.filter(
        tournament=tournament,
        participant1=challenger,
        status__in=active_statuses
    ).exists():
        messages.warning(request, "Możesz mieć tylko jedno aktywne wyzwanie w tym samym czasie.")
        return redirect('tournaments:details_ladder', pk=tournament.pk)

    if TournamentsMatch.objects.filter(
        tournament=tournament,
        participant2=challenged,
        status__in=active_statuses
    ).exists():
        messages.warning(request, f"Gracz {challenged.display_name} jest już zaangażowany w inne wyzwanie. Spróbuj ponownie później.")
        return redirect('tournaments:details_ladder', pk=tournament.pk)
    
    # --- POPRAWKA: Ujednolicenie logiki z widokiem drabinki ---
    # Sprawdzamy blokadę rewanżu tylko w obrębie bieżącej, najwyższej rundy.
    from django.db.models import Max
    current_max_round = tournament.matches.aggregate(max_round=Max('round_number')).get('max_round')

    if current_max_round:
        if TournamentsMatch.objects.filter(
            Q(participant1=challenger, participant2=challenged) |
            Q(participant1=challenged, participant2=challenger),
            tournament=tournament,
            status=TournamentsMatch.Status.COMPLETED.value,
            round_number=current_max_round
        ).exists():
            messages.error(request, f"Nie możesz wyzwać gracza {challenged.display_name}, ponieważ rozegraliście już mecz w tej rundzie.")
            return redirect('tournaments:details_ladder', pk=tournament.pk)

    if ChallengeRejection.objects.filter(
        tournament=tournament,
        rejecting_participant=challenged,
        challenger_participant=challenger
    ).exists():
        messages.error(request, f"Nie możesz wyzwać gracza {challenged.display_name}, ponieważ odrzucił on już Twoje wyzwanie. Spróbuj ponownie, gdy jeden z Was rozegra inny mecz.")
        return redirect('tournaments:details_ladder', pk=tournament.pk)

    from django.db.models import Max
    current_round_num = tournament.matches.aggregate(max_round=Max('round_number')).get('max_round') or 1

    # Poprawione obliczanie indeksu: licz mecze tylko w bieżącej rundzie
    next_match_index = tournament.matches.filter(round_number=current_round_num).count() + 1

    new_match = TournamentsMatch.objects.create(
        tournament=tournament,
        participant1=challenger,
        participant2=challenged,
        status=TournamentsMatch.Status.WAITING.value,
        round_number=current_round_num,
        match_index=next_match_index
    )

    messages.success(request, f"Rzucono wyzwanie graczowi {challenged.display_name}! Mecz został utworzony i oczekuje na ustalenie terminu.")
    
    if challenged.user:
        notification_message = f"Gracz {challenger.display_name} rzucił Ci wyzwanie w turnieju '{tournament.name}'."
        notify_user(challenged.user, notification_message, 'info')

    return redirect('tournaments:details_ladder', pk=tournament.pk)


@login_required
@require_POST
def cancel_challenge(request, pk, match_pk):
    """
    Pozwala graczowi, który rzucił wyzwanie, na jego anulowanie (challenger),
    a graczowi wyzwanemu na jego odrzucenie (challenged), o ile mecz nie został jeszcze rozpoczęty.
    """
    tournament = get_object_or_404(Tournament, pk=pk, tournament_type=Tournament.TournamentType.LADDER.value)
    match = get_object_or_404(TournamentsMatch, pk=match_pk, tournament=tournament)

    is_challenger = match.participant1 and request.user == match.participant1.user
    is_challenged = match.participant2 and request.user == match.participant2.user

    if not (is_challenger or is_challenged):
        messages.error(request, "Nie masz uprawnień do wykonania tej akcji.")
        return redirect('tournaments:details_ladder', pk=tournament.pk)

    cancellable_statuses = [TournamentsMatch.Status.WAITING.value, TournamentsMatch.Status.SCHEDULED.value]
    if match.status not in cancellable_statuses:
        messages.error(request, "Nie można anulować/odrzucić wyzwania, ponieważ mecz już się rozpoczął lub został zakończony.")
        return redirect('tournaments:details_ladder', pk=tournament.pk)

    other_party_user = None
    if is_challenger:
        other_party_user = match.participant2.user if match.participant2 else None
        success_message = "Twoje wyzwanie zostało pomyślnie anulowane."
        notification_message = f"Gracz {request.user.username} anulował swoje wyzwanie w turnieju '{tournament.name}'."
    else:
        if ChallengeRejection.objects.filter(tournament=tournament, rejecting_participant=match.participant2).exists():
            messages.error(request, "Możesz odrzucić tylko jedno wyzwanie w danej rundzie. Zagraj swój następny mecz, aby móc odrzucić kolejne.")
            return redirect('tournaments:details_ladder', pk=tournament.pk)

        other_party_user = match.participant1.user if match.participant1 else None
        success_message = "Wyzwanie zostało pomyślnie odrzucone."
        notification_message = f"Gracz {request.user.username} odrzucił Twoje wyzwanie w turnieju '{tournament.name}'."
        
        ChallengeRejection.objects.create(
            tournament=tournament,
            rejecting_participant=match.participant2,
            challenger_participant=match.participant1
        )
        messages.info(request, "Informacja o odrzuceniu została zapisana. Nie będziesz mógł być ponownie wyzwany przez tego gracza do czasu rozegrania meczu.")

    match.delete()
    messages.success(request, success_message)

    if other_party_user:
        notify_user(other_party_user, notification_message, 'warning')

    return redirect('tournaments:details_ladder', pk=tournament.pk)


@login_required
def create_match(request, pk):
    """Widok do ręcznego tworzenia nowego meczu."""
    tournament = get_object_or_404(Tournament, pk=pk)

    if request.user != tournament.created_by and not request.user.is_staff:
        messages.error(request, 'Brak uprawnień.')
        return redirect('tournaments:manage')

    if request.method == 'POST':
        # --- ZMIANA: Przekaż `user` i `has_full_permissions` do formularza ---
        form = TournamentsMatchForm(request.POST, tournament=tournament, user=request.user, has_full_permissions=True)
        if form.is_valid():
            match = form.save(commit=False)
            match.tournament = tournament
            match.save()
            messages.success(request, 'Mecz został utworzony.')
            # --- POPRAWKA: Przekieruj na URL powrotny lub domyślny ---
            return redirect('tournaments:manage_matches', pk=tournament.pk)
        else:
            messages.error(request, 'W formularzu wystąpiły błędy. Sprawdź dane.')
    else:
        try:
            last_match = TournamentsMatch.objects.filter(tournament=tournament).order_by('-round_number', '-match_index').first()
            if last_match:
                initial_round = last_match.round_number
                initial_index = last_match.match_index + 1
            else:
                initial_round = 1
                initial_index = 1
        except TournamentsMatch.DoesNotExist:
            initial_round = 1
            initial_index = 1

        from django.utils import timezone
        initial = {
            'round_number': initial_round, 
            'match_index': initial_index,
            'scheduled_time': timezone.now().strftime('%Y-%m-%dT%H:%M')
        }
        # --- ZMIANA: Przekaż `user` i `has_full_permissions` do formularza ---
        form = TournamentsMatchForm(initial=initial, tournament=tournament, user=request.user, has_full_permissions=True)

    context = {
        'form': form,
        'tournament': tournament,
        'is_editing': False,
        'has_full_permissions': True,  # Organizator zawsze ma pełne uprawnienia
        'next_url': request.GET.get('next', redirect('tournaments:manage_matches', pk=tournament.pk).url)
    }
    return render(request, 'tournaments/match_form.html', context)


@login_required
def edit_match(request, pk, match_pk):
    """Widok do edycji istniejącego meczu, w tym wyników."""
    tournament = get_object_or_404(Tournament, pk=pk)
    match = get_object_or_404(TournamentsMatch, pk=match_pk, tournament=tournament)

    is_organizer = request.user == tournament.created_by
    is_participant_in_match = (match.participant1 and request.user == match.participant1.user) or \
                              (match.participant2 and request.user == match.participant2.user)

    # Użytkownik ma pełne uprawnienia, jeśli jest organizatorem lub uczestnikiem aktywnego turnieju.
    has_full_permissions = is_organizer or (is_participant_in_match and tournament.status == Tournament.Status.ACTIVE.value)

    # Użytkownik może edytować wynik "na żywo", jeśli mecz jest w toku.
    can_live_update = match.status == TournamentsMatch.Status.IN_PROGRESS.value

    # --- ZMIANA: Użytkownik może rozpocząć mecz, jeśli nie ma pełnych uprawnień, a mecz czeka na rozpoczęcie. ---
    startable_statuses = [TournamentsMatch.Status.WAITING.value, TournamentsMatch.Status.SCHEDULED.value]
    can_start_match = not has_full_permissions and match.status in startable_statuses

    if tournament.status == Tournament.Status.FINISHED.value:
        messages.error(request, 'Nie można edytować meczu, ponieważ turniej jest zakończony.')
        # --- POPRAWKA: Użyj funkcji pomocniczej do wygenerowania URL ---
        return redirect(get_tournament_details_url(tournament))

    # --- ZMIANA: Zezwól na dostęp, jeśli użytkownik ma jakiekolwiek uprawnienia (pełne, live update lub start). ---
    # Jeśli użytkownik nie ma żadnych z tych uprawnień, zablokuj dostęp.
    if not has_full_permissions and not can_live_update and not can_start_match:
        messages.error(request, 'Brak uprawnień do edycji tego meczu.')
        # --- POPRAWKA: Użyj funkcji pomocniczej do wygenerowania URL ---
        return redirect(get_tournament_details_url(tournament))

    # --- ZMIANA: Pobierz URL powrotny z parametru 'next' ---
    # Jeśli parametr 'next' nie jest dostępny, użyj domyślnego URL do strony turnieju.
    # --- POPRAWKA: Użyj funkcji pomocniczej do wygenerowania URL ---
    default_next_url = get_tournament_details_url(tournament)
    next_url = request.GET.get('next', default_next_url)

    # --- ZMIANA: Wybierz odpowiedni formularz i szablon na podstawie typu turnieju ---
    if tournament.tournament_type == Tournament.TournamentType.AMERICANO.value:
        form_class = AmericanoMatchForm
        template_name = 'tournaments/americano_match_form.html'
    else:
        # Domyślne zachowanie dla innych typów turniejów
        form_class = ParticipantMatchForm
        template_name = 'tournaments/participant_match_form.html'
    
    # Sprawdź, czy późniejsze rundy się nie rozpoczęły, ale ignoruj tę logikę dla meczu o 3. miejsce (round_number=0)
    if tournament.tournament_type in [Tournament.TournamentType.SINGLE_ELIMINATION, Tournament.TournamentType.SWISS] and match.round_number > 0:
        subsequent_rounds_started = TournamentsMatch.objects.filter(
            tournament=tournament,
            round_number__gt=match.round_number,
            status__in=[TournamentsMatch.Status.IN_PROGRESS.value, TournamentsMatch.Status.COMPLETED.value]
        ).exists()
        if subsequent_rounds_started:
            messages.error(
                request, f'Nie można edytować meczu z rundy {match.round_number}, ponieważ mecze w późniejszych rundach już się rozpoczęły lub zostały zakończone.'
            )
            return redirect('tournaments:details_elimination', pk=tournament.pk)

    if request.method == 'POST':
        # Przygotuj argumenty dla konstruktora formularza
        form_kwargs = {'instance': match, 'tournament': tournament}
        if form_class is not AmericanoMatchForm:
            # Argumenty specyficzne dla starych formularzy
            form_kwargs.update({
                'has_full_permissions': has_full_permissions,
                'can_start_match': can_start_match
            })
            if not has_full_permissions:
                form_kwargs['read_only_fields'] = ['winner']

        form = form_class(request.POST, **form_kwargs)

        if form.is_valid():
            updated_match = form.save(commit=False)

            # --- ZMIANA: Zapisz historię wyniku tylko, jeśli się zmienił ---
            last_history_entry = MatchScoreHistory.objects.filter(match=updated_match).order_by('-updated_at').first()
            
            scores_changed = True  # Domyślnie zakładamy, że wynik się zmienił
            if last_history_entry:
                # Porównaj każdy wynik z ostatnim wpisem
                if (last_history_entry.set1_p1_score == updated_match.set1_p1_score and
                    last_history_entry.set1_p2_score == updated_match.set1_p2_score and
                    last_history_entry.set2_p1_score == updated_match.set2_p1_score and
                    last_history_entry.set2_p2_score == updated_match.set2_p2_score and
                    last_history_entry.set3_p1_score == updated_match.set3_p1_score and
                    last_history_entry.set3_p2_score == updated_match.set3_p2_score):
                    scores_changed = False

            # Dla Americano, status jest ustawiany w formularzu, więc go przypisujemy
            if form_class is AmericanoMatchForm:
                updated_match.status = form.cleaned_data['status']
                # W Americano nie ma zwycięzcy meczu, więc upewniamy się, że jest None
                updated_match.winner = None

            updated_match.save()
            # Zapisz historię tylko, jeśli wynik się zmienił lub nie ma poprzednich wpisów
            if scores_changed:
                MatchScoreHistory.objects.create(
                    match=updated_match,
                    updated_by=request.user,
                    set1_p1_score=updated_match.set1_p1_score,
                    set1_p2_score=updated_match.set1_p2_score,
                    set2_p1_score=updated_match.set2_p1_score,
                    set2_p2_score=updated_match.set2_p2_score,
                    set3_p1_score=updated_match.set3_p1_score,
                    set3_p2_score=updated_match.set3_p2_score,
                )
            messages.success(request, 'Mecz został zaktualizowany.')

            # --- LOGIKA DLA MEXICANO: Sprawdź, czy runda jest zakończona i wygeneruj następną ---
            if (tournament.tournament_type == Tournament.TournamentType.AMERICANO.value and
                tournament.config.scheduling_type == 'DYNAMIC' and
                updated_match.status == TournamentsMatch.Status.COMPLETED.value):
                
                current_round_number = updated_match.round_number
                all_matches_in_round = TournamentsMatch.objects.filter(
                    tournament=tournament,
                    round_number=current_round_number
                )
                is_round_complete = not all_matches_in_round.exclude(
                    status=TournamentsMatch.Status.COMPLETED.value
                ).exists()

                if is_round_complete:
                    standings_list = calculate_americano_standings(tournament)
                    count, message = generate_next_mexicano_round(tournament, tournament.config, standings_list)
                    if count > 0:
                        messages.info(request, message)

            if tournament.tournament_type == Tournament.TournamentType.LADDER and updated_match.status == TournamentsMatch.Status.COMPLETED.value:
                winner = updated_match.winner
                challenger = updated_match.participant1
                challenged = updated_match.participant2

                if winner and challenger and challenged and winner.id == challenger.id:
                    challenger_seed = challenger.seed_number
                    challenged_seed = challenged.seed_number

                    challenger.seed_number = challenged_seed
                    challenged.seed_number = challenger_seed

                    challenger.save(update_fields=['seed_number'])
                    challenged.save(update_fields=['seed_number'])

                    messages.info(request, f"Ranking został zaktualizowany! {challenger.display_name} przejął pozycję {challenged.display_name}.")
                
                rejections_to_clear = ChallengeRejection.objects.filter(
                    Q(rejecting_participant=challenger) | Q(rejecting_participant=challenged) |
                    Q(challenger_participant=challenger) | Q(challenger_participant=challenged),
                    tournament=tournament
                )
                rejections_to_clear.delete()

            # --- ZMIANA: Automatyczne generowanie następnej rundy w turnieju pucharowym ---
            if tournament.tournament_type == Tournament.TournamentType.SINGLE_ELIMINATION.value and updated_match.status == TournamentsMatch.Status.COMPLETED.value:
                current_round_number = updated_match.round_number
                
                # Sprawdź, czy wszystkie mecze w bieżącej rundzie są zakończone
                # (ignorujemy mecz o 3. miejsce, który ma round_number=0)
                if current_round_number > 0:
                    all_matches_in_round = TournamentsMatch.objects.filter(
                        tournament=tournament,
                        round_number=current_round_number
                    )
                    
                    is_round_complete = not all_matches_in_round.exclude(
                        status=TournamentsMatch.Status.COMPLETED.value
                    ).exists()

                    if is_round_complete:
                        # Jeśli runda jest kompletna, wygeneruj następną
                        count, message = generate_next_elimination_round(tournament, current_round_number)
                        messages.info(request, message)

            # --- ZMIANA: Obsługa Double Elimination ---
            if tournament.tournament_type == Tournament.TournamentType.DOUBLE_ELIMINATION.value and updated_match.status == TournamentsMatch.Status.COMPLETED.value:
                advance_double_elimination(tournament, updated_match)

            # --- ZMIANA: Obsługa Systemu Szwajcarskiego (Generowanie następnej rundy) ---
            if tournament.tournament_type == Tournament.TournamentType.SWISS and updated_match.status == TournamentsMatch.Status.COMPLETED.value:
                current_round_number = updated_match.round_number
                
                # Sprawdź, czy jesteśmy w fazie grupowej czy pucharowej
                swiss_rounds = tournament.swiss_system_config.number_of_rounds
                
                all_matches_in_round = TournamentsMatch.objects.filter(
                    tournament=tournament,
                    round_number=current_round_number
                )
                is_round_complete = not all_matches_in_round.exclude(
                    status=TournamentsMatch.Status.COMPLETED.value
                ).exists()

                if is_round_complete:
                    if current_round_number <= swiss_rounds:
                        # Faza grupowa lub przejście do fazy pucharowej
                        # generate_next_swiss_round sam zdecyduje czy robić kolejną rundę swiss czy playoff
                        try:
                            pairs_count, message = generate_next_swiss_round(tournament, tournament.swiss_system_config)
                            if pairs_count > 0:
                                messages.success(request, message)
                            else:
                                messages.info(request, message)
                        except Exception as e:
                            messages.error(request, f'Błąd podczas generowania nowej rundy: {str(e)}')
                    else:
                        # Faza pucharowa (Play-offy) - używamy standardowej logiki eliminacji
                        try:
                            count, message = generate_next_elimination_round(tournament, current_round_number)
                            messages.info(request, message)
                        except Exception as e:
                            messages.error(request, f'Błąd generowania rundy pucharowej: {str(e)}')

            # --- ZMIANA: Poprawka przekierowania dla systemu szwajcarskiego ---
            if tournament.tournament_type == Tournament.TournamentType.SWISS:
                return redirect('tournaments:details_swiss', pk=tournament.pk)

            # --- ZMIANA: Przekieruj na URL powrotny ---
            return redirect(next_url)
        else:
            messages.error(request, 'W formularzu wystąpiły błędy. Sprawdź dane.')
    else:
        from django.utils import timezone
        # --- ZMIANA: Zawsze ustawiaj datę na aktualną podczas ładowania formularza edycji ---
        match.scheduled_time = timezone.now().strftime('%Y-%m-%dT%H:%M')

        form_kwargs = {'instance': match, 'tournament': tournament}
        if form_class is not AmericanoMatchForm:
            form_kwargs.update({
                'has_full_permissions': has_full_permissions,
                'can_start_match': can_start_match
            })
            if not has_full_permissions:
                form_kwargs['read_only_fields'] = ['winner']

        form = form_class(**form_kwargs)

    is_doubles = tournament.match_format == 'DBL'
    p1_partner = None
    p2_partner = None
    if is_doubles:
        if match.participant1:
            p1_partner = match.participant1.members.select_related('user').first()
        if match.participant2:
            p2_partner = match.participant2.members.select_related('user').first()

    context = {
        'form': form,
        'tournament': tournament,
        'match': match,
        'is_editing': True,
        'has_full_permissions': has_full_permissions,
        'next_url': next_url,
        'is_doubles': is_doubles,
        'p1_partner': p1_partner,
        'p2_partner': p2_partner,
    }
    return render(request, template_name, context)


@login_required
@require_POST
def start_match(request, pk, match_pk):
    """
    Pozwala każdemu zalogowanemu użytkownikowi na zmianę statusu meczu z 'Zaplanowany' na 'W trakcie'.
    """
    tournament = get_object_or_404(Tournament, pk=pk)
    match = get_object_or_404(TournamentsMatch, pk=match_pk, tournament=tournament)

    if match.status == TournamentsMatch.Status.SCHEDULED.value:
        match.status = TournamentsMatch.Status.IN_PROGRESS.value
        match.save(update_fields=['status'])
        messages.success(request, f"Mecz pomiędzy {match.participant1} a {match.participant2} został rozpoczęty.")
    else:
        messages.warning(request, "Nie można rozpocząć tego meczu, ponieważ nie jest on w statusie 'Zaplanowany'.")

    # Przekieruj z powrotem na stronę szczegółów turnieju
    return redirect(get_tournament_details_url(tournament))


def get_tournament_details_url(tournament):
    """Zwraca URL do strony szczegółów turnieju na podstawie jego typu."""
    if tournament.tournament_type == Tournament.TournamentType.ROUND_ROBIN.value:
        return redirect('tournaments:details_round_robin', pk=tournament.pk).url
    elif tournament.tournament_type == Tournament.TournamentType.SINGLE_ELIMINATION.value:
        return redirect('tournaments:details_elimination', pk=tournament.pk).url
    elif tournament.tournament_type == Tournament.TournamentType.DOUBLE_ELIMINATION.value:
        return redirect('tournaments:details_double_elimination', pk=tournament.pk).url
    elif tournament.tournament_type == Tournament.TournamentType.LADDER.value:
        return redirect('tournaments:details_ladder', pk=tournament.pk).url
    elif tournament.tournament_type == Tournament.TournamentType.AMERICANO.value:
        return redirect('tournaments:details_americano', pk=tournament.pk).url
    # Domyślny URL, jeśli typ jest nieznany (fallback)
    return redirect('tournaments:manage').url


@login_required
def live_match_view(request, pk, match_pk):
    """
    Wyświetla stronę "na żywo" dla danego meczu, zawierającą aktualny wynik,
    historię zmian i czat.
    """
    tournament = get_object_or_404(Tournament, pk=pk)
    match = get_object_or_404(TournamentsMatch.objects.select_related(
        'tournament', 'participant1', 'participant2', 'participant3', 'participant4'
    ), pk=match_pk, tournament=tournament)

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST' and request.user.is_authenticated:
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            content = form.cleaned_data.get('content')
            images = request.FILES.getlist('images')

            # Utwórz wiadomość
            message = TournamentMatchChatMessage.objects.create(
                match=match,
                sender=request.user,
                content=content
            )

            image_objects = []
            # Dodaj załączone obrazy do wiadomości
            for image_file in images:
                chat_image = TournamentMatchChatImage.objects.create(message=message, image=image_file)
                image_objects.append(chat_image)
            
            if is_ajax:
                images_data = [{'url': img.image.url} for img in image_objects]
                message_data = {
                    'id': message.id,
                    'sender_name': message.sender.get_full_name() or message.sender.username,
                    'content': message.content,
                    'timestamp': message.timestamp.isoformat(),
                    'is_sent_by_user': True, # Zawsze prawda, bo to jest wiadomość wysyłana
                    'images': images_data,
                }
                return JsonResponse({'message': message_data}, status=201)
            else:
                return redirect('tournaments:live_match', pk=pk, match_pk=match_pk)
        elif is_ajax:
            # Jeśli formularz jest nieprawidłowy i to żądanie AJAX, zwróć błędy
            return JsonResponse({'errors': form.errors}, status=400)
        # Dla standardowego POST z błędami, strona zostanie wyrenderowana ponownie poniżej
    else:
        form = MessageForm()

    # Pobieranie historii wyników
    score_history = match.score_history.select_related('updated_by').order_by('-updated_at')
    
    now = timezone.now()
    for entry in score_history:
        time_difference = now - entry.updated_at
        entry.is_recent = time_difference.total_seconds() <= 3600  # 3600 sekund = 60 minut

    # Pobieranie wiadomości czatu
    chat_messages = TournamentMatchChatMessage.objects.filter(match=match).select_related('sender').prefetch_related('images').order_by('timestamp')

    # Ustawienie URL powrotnego
    default_next_url = get_tournament_details_url(tournament)
    next_url = request.GET.get('next', default_next_url)

    context = {
        'tournament': tournament,
        'match': match,
        'score_history': score_history,
        'chat_messages': chat_messages,
        'form': form,
    }
    context['next_url'] = next_url
    return render(request, 'tournaments/live_match_view.html', context)


@login_required
@require_POST
def delete_match(request, pk, match_pk):
    """Usuwa mecz (tylko POST)."""
    tournament = get_object_or_404(Tournament, pk=pk)
    match = get_object_or_404(TournamentsMatch, pk=match_pk, tournament=tournament)

    if request.user != tournament.created_by and not request.user.is_staff:
        messages.error(request, 'Brak uprawnień.')
        return redirect('tournaments:manage_matches', pk=tournament.pk)

    match.delete()
    messages.success(request, 'Mecz został usunięty.')
    return redirect('tournaments:manage_matches', pk=tournament.pk)


@login_required
@require_POST
def reset_leaderboard_locks(request, pk):
    """
    Resetuje blokady w turnieju drabinkowym i rozpoczyna nową "rundę".
    - Usuwa wszystkie blokady odrzuceń (ChallengeRejection).
    - Przenosi wszystkie aktywne (niezakończone) mecze do nowej rundy.
    """
    tournament = get_object_or_404(Tournament, pk=pk)

    if request.user != tournament.created_by and not request.user.is_staff:
        messages.error(request, "Brak uprawnień do wykonania tej akcji.")
        return redirect('tournaments:manage_matches', pk=pk)

    if tournament.tournament_type != Tournament.TournamentType.LADDER.value:
        messages.error(request, "Ta funkcja jest dostępna tylko dla turniejów drabinkowych.")
        return redirect('tournaments:manage_matches', pk=pk)

    rejections_cleared_count, _ = ChallengeRejection.objects.filter(tournament=tournament).delete()

    from django.db.models import Max
    current_max_round = tournament.matches.aggregate(max_round=Max('round_number')).get('max_round')
    new_round_number = (current_max_round or 0) + 1

    active_statuses = [
        TournamentsMatch.Status.WAITING.value,
        TournamentsMatch.Status.SCHEDULED.value,
        TournamentsMatch.Status.IN_PROGRESS.value
    ]
    matches_to_move = tournament.matches.filter(status__in=active_statuses)
    moved_matches_count = matches_to_move.update(round_number=new_round_number)

    # --- POPRAWKA ---
    # Jeśli po resecie nie ma żadnych meczów w nowej rundzie (bo np. wszystkie były zakończone),
    # Max('round_number') wciąż będzie wskazywać na starą rundę.
    # Aby temu zapobiec, tworzymy "pusty" mecz techniczny w nowej rundzie, jeśli żaden tam nie istnieje.
    # To gwarantuje, że Max() zawsze zwróci poprawny numer nowej rundy.
    if not tournament.matches.filter(round_number=new_round_number).exists():
        TournamentsMatch.objects.create(
            tournament=tournament,
            round_number=new_round_number,
            match_index=0,  # Używamy indeksu 0 dla meczu technicznego
            status=TournamentsMatch.Status.CANCELLED.value
        )

    messages.success(request, f"Rozpoczęto nową rundę ({new_round_number}) w drabince.")
    if rejections_cleared_count > 0:
        messages.info(request, f"Usunięto {rejections_cleared_count} blokad(y) odrzuconych wyzwań.")
    if moved_matches_count > 0:
        messages.info(request, f"Przeniesiono {moved_matches_count} aktywnych meczów do nowej rundy.")
    if rejections_cleared_count == 0 and moved_matches_count == 0:
        messages.info(request, "Nie znaleziono żadnych aktywnych blokad ani meczów do przeniesienia.")

    return redirect('tournaments:manage_matches', pk=pk)


@login_required
@require_POST
def add_reaction(request, match_pk):
    """
    Widok AJAX do dodawania/usuwania reakcji na mecz.
    """
    try:
        match = get_object_or_404(TournamentsMatch, pk=match_pk)
        emoji = request.POST.get('emoji')

        if not emoji or emoji not in [choice[0] for choice in MatchReaction.REACTION_CHOICES]:
            return JsonResponse({'status': 'error', 'message': 'Nieprawidłowa reakcja.'}, status=400)

        # Sprawdź, czy reakcja już istnieje
        reaction, created = MatchReaction.objects.get_or_create(
            match=match,
            user=request.user,
            emoji=emoji
        )

        if not created:
            # Jeśli reakcja już istniała, usuwamy ją (toggle off)
            reaction.delete()
            action = 'removed'
        else:
            action = 'added'

        # Zwróć zaktualizowaną liczbę reakcji danego typu
        reactions_count = MatchReaction.objects.filter(match=match, emoji=emoji).count()
        return JsonResponse({'status': 'ok', 'action': action, 'count': reactions_count})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# --- Implementacja logiki Advance dla Double Elimination (nadpisanie placeholdera) ---
def advance_double_elimination(tournament, match):
    """
    Logika awansu dla Double Elimination z wykorzystaniem konwencji indeksowania:
    WB: match_index < 1000
    LB: match_index >= 1000
    Grand Final: Specjalna runda (max WB round + 1)
    """
    if not match.winner:
        return

    # Jeśli to Wielki Finał (Runda 99), nie ma dalszego awansu ani spadku
    if match.round_number == 99:
        return

    loser = match.participant1 if match.winner == match.participant2 else match.participant2
    is_lb = is_match_in_losers_bracket(tournament, match)
    
    # Oblicz max rundę WB (aby wykryć finał)
    # Liczba uczestników determinuje rozmiar drabinki
    # np. 8 graczy -> WB ma 3 rundy (ćwierć, pół, finał). 2^3 = 8.
    # log2(8) = 3.
    # Pobierzmy liczbę uczestników z konfiguracji lub liczby graczy
    total_participants = tournament.participants.count()
    # Zaokrąglenie do potęgi 2
    bracket_size = 2**math.ceil(math.log2(total_participants))
    total_wb_rounds = int(math.log2(bracket_size))

    # --- SCENARIUSZ 1: Mecz w Winners Bracket (WB) ---
    if not is_lb:
        # 1. Zwycięzca idzie dalej w WB
        if match.round_number < total_wb_rounds:
            next_wb_round = match.round_number + 1
            next_wb_index = math.ceil(match.match_index / 2)
            target_match = get_or_create_match(tournament, next_wb_round, next_wb_index)
            
            # Ustal slot (1 lub 2)
            if match.match_index % 2 != 0: # Nieparzysty -> Slot 1
                target_match.participant1 = match.winner
            else: # Parzysty -> Slot 2
                target_match.participant2 = match.winner
            target_match.save()
        else:
            # Zwycięzca finału WB idzie do Wielkiego Finału (Grand Final)
            # Grand Final to runda total_wb_rounds + 1 (lub inna wysoka liczba)
            # Przyjmijmy konwencję: Grand Final ma round_number = total_wb_rounds + 2 (dla bezpieczeństwa)
            # i match_index = 1.
            gf_round = total_wb_rounds + 2 # +2 bo LB ma więcej rund, ale dla uproszczenia sortowania dajmy wysoko
            # W rzeczywistości LB ma 2*(N-1) rund. Np dla 3 rund WB, LB ma 4 rundy.
            # Bezpieczniej użyć bardzo wysokiego numeru rundy dla GF, np. 99.
            gf_round = 99 
            
            target_match = get_or_create_match(tournament, gf_round, 1)
            target_match.participant1 = match.winner # Zwycięzca WB wchodzi jako P1
            target_match.save()

        # 2. Przegrany spada do Losers Bracket (LB)
        if loser: # Jeśli był walkower/bye i nie ma przegranego, nic nie robimy
            lb_round = get_lb_drop_round(match.round_number)
            
            # Obliczanie indeksu w LB
            # Dla WB R1 -> LB R1: Indeks mapuje się prosto (1->1, 2->1, 3->2, 4->2)
            # Dla WB R>1 -> LB R(parzyste): Indeks mapuje się bezpośrednio, ale z offsetem 1000
            
            if match.round_number == 1:
                lb_index = 1000 + math.ceil(match.match_index / 2)
                target_lb_match = get_or_create_match(tournament, lb_round, lb_index)
                # Slotowanie: Mecz 1 i 2 z WB idą do Meczu 1 LB.
                if match.match_index % 2 != 0:
                    target_lb_match.participant1 = loser
                else:
                    target_lb_match.participant2 = loser
                target_lb_match.save()
            else:
                # Spadają do rund parzystych LB (2, 4, 6...)
                # Tam grają ze zwycięzcami poprzedniej rundy LB.
                # Zwykle spadkowicze zajmują Slot 1 (lub 2, kwestia konwencji).
                lb_index = 1000 + match.match_index # Zachowujemy indeks (np. WB Mecz 1 -> LB Mecz 1)
                target_lb_match = get_or_create_match(tournament, lb_round, lb_index)
                target_lb_match.participant1 = loser # Spadkowicz jako P1
                target_lb_match.save()

    # --- SCENARIUSZ 2: Mecz w Losers Bracket (LB) ---
    else:
        # Zwycięzca idzie dalej w LB
        # Sprawdź czy to finał LB
        # Finał LB jest wtedy, gdy w danej rundzie jest tylko 1 mecz.
        # Ale musimy uważać, bo w LB rundy parzyste i nieparzyste mają różną liczbę meczów.
        
        current_lb_round_index = match.round_number # To jest np. 1, 2, 3...
        # Czy to ostatnia runda LB? LB ma 2*(WB_Rounds) - 2 rund.
        max_lb_rounds = (total_wb_rounds * 2) - 2
        
        if match.round_number < max_lb_rounds:
            next_lb_round = match.round_number + 1
            
            # Logika indeksów w LB
            # Jeśli obecna runda jest NIEPARZYSTA (1, 3...): Zwycięzcy grają ze spadkowiczami w nast. rundzie.
            # Indeks w nast. rundzie (parzystej) jest taki sam.
            # Np. LB R1 M1 -> LB R2 M1.
            if match.round_number % 2 != 0:
                next_lb_index = match.match_index # 1001 -> 1001
                target_match = get_or_create_match(tournament, next_lb_round, next_lb_index)
                target_match.participant2 = match.winner # Spadkowicz jest na P1, zwycięzca LB na P2
            else:
                # Jeśli obecna runda jest PARZYSTA (2, 4...): Zwycięzcy grają między sobą.
                # Redukcja liczby meczów o połowę.
                # 1001, 1002 -> 1001.
                raw_index = match.match_index - 1000
                next_raw_index = math.ceil(raw_index / 2)
                next_lb_index = 1000 + next_raw_index
                
                target_match = get_or_create_match(tournament, next_lb_round, next_lb_index)
                if raw_index % 2 != 0:
                    target_match.participant1 = match.winner
                else:
                    target_match.participant2 = match.winner
            
            target_match.save()
        
        else:
            # Zwycięzca finału LB idzie do Grand Final
            gf_round = 99
            target_match = get_or_create_match(tournament, gf_round, 1)
            target_match.participant2 = match.winner # Zwycięzca LB wchodzi jako P2
            target_match.save()
