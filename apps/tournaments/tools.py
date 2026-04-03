from .models import TournamentsMatch, Tournament, MatchReaction
from django.db.models import Q, Max
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
from types import SimpleNamespace
from django.urls import reverse
from decimal import Decimal

def get_tournament_matches_as_friendly(user, filters=None):
    """
    Pobiera wszystkie mecze turniejowe danego użytkownika i konwertuje je
    do formatu przypominającego mecze z modelu `matches.Match`.

    Args:
        user (User): Obiekt zalogowanego użytkownika.
        filters (dict, optional): Słownik filtrów do zastosowania. Domyślnie None.

    Returns:
        list: Lista słowników, gdzie każdy słownik reprezentuje mecz
              w ujednoliconym formacie.
    """
    # 1. Znajdź wszystkich uczestników (Participant) powiązanych z danym użytkownikiem
    user_participant_ids = list(user.tournament_participations.values_list('id', flat=True))

    if not user_participant_ids:
        return []

    # 2. Pobierz wszystkie mecze, w których brał udział którykolwiek z tych uczestników i które są zakończone
    qs = TournamentsMatch.objects.filter(
        Q(participant1_id__in=user_participant_ids) |
        Q(participant2_id__in=user_participant_ids) |
        Q(participant3_id__in=user_participant_ids) |
        Q(participant4_id__in=user_participant_ids), # Upewnij się, że użytkownik jest uczestnikiem
        status=TournamentsMatch.Status.COMPLETED.value
    ).select_related(
        'tournament',
        'participant1__user', 'participant2__user',
        'participant3__user', 'participant4__user'
    ).order_by('-scheduled_time')

    # Wyklucz mecze z pierwszej rundy turnieju pucharowego, gdzie p2 to BYE (lub null)
    qs = qs.exclude(
        tournament__tournament_type__in=[
            Tournament.TournamentType.SINGLE_ELIMINATION.value,
            Tournament.TournamentType.DOUBLE_ELIMINATION.value
        ],
        round_number=1,
        participant2__isnull=True
    )

    # 2.1. Zastosuj filtr match_double do querysetu
    if filters and filters.get("match_double") is not None:
        if filters["match_double"] == 0: # Mecze singlowe
            # Mecz jest singlowy, jeśli nie jest deblowy.
            # Mecz jest deblowy, jeśli (p3 i p4 istnieją) LUB (format turnieju to DBL).
            # Zatem singiel oznacza NIE ((p3 i p4 istnieją) LUB (format turnieju to DBL)).
            # Co jest równoważne (NIE (p3 i p4 istnieją)) ORAZ (format turnieju to NIE DBL).
            # NIE (p3 i p4 istnieją) oznacza (p3 jest null LUB p4 jest null).
            qs = qs.filter(Q(participant3__isnull=True) | Q(participant4__isnull=True)).exclude(tournament__match_format=Tournament.MatchFormat.DOUBLES.value)
        elif filters["match_double"] == 1: # Mecze deblowe
            # Mecz jest deblowy, jeśli (p3 i p4 istnieją) LUB (format turnieju to DBL).
            qs = qs.filter(Q(participant3__isnull=False, participant4__isnull=False) | Q(tournament__match_format=Tournament.MatchFormat.DOUBLES.value))

    # 2.2. Zastosuj filtry daty do querysetu
    if filters:
        if filters.get("last_days") in [7, 30]:
            since = timezone.now().date() - timedelta(days=int(filters["last_days"]))
            qs = qs.filter(scheduled_time__date__gte=since)
        elif filters.get("last_days") and str(filters["last_days"]).isdigit() and int(filters["last_days"]) > 0: # Konkretny rok
            qs = qs.filter(scheduled_time__year=filters["last_days"])
        elif filters.get("this_year"):
            qs = qs.filter(scheduled_time__year=timezone.now().year)

    tournament_matches = list(qs) # Pobierz wszystkie przefiltrowane obiekty TournamentsMatch

    converted_matches = []
    for match in tournament_matches:
        if match.tournament.tournament_type == Tournament.TournamentType.AMERICANO:
            continue

        # 3. Rozpoznaj, czy mecz jest deblowy
        # Mecz jest deblowy, jeśli ma więcej niż 2 uczestników lub format turnieju to debel.
        is_double = (
            (match.participant1 and match.participant2 and match.participant3 and match.participant4) or
            match.tournament.match_format == Tournament.MatchFormat.DOUBLES
        )

        # 4. Mapowanie graczy i wyników
        # W `matches.Match` p1/p3 to drużyna 1, a p2/p4 to drużyna 2.
        # W `tournaments.TournamentsMatch` p1/p2 (lub p1/p4 w Americano) to drużyna 1, a p3/p4 (lub p2/p3) to drużyna 2.
        # Musimy dokonać mapowania. Dla uproszczenia przyjmijmy standardowe parowanie.
        # W Americano/Mexicano (debel) team1 to p1+p4, team2 to p2+p3.
        if match.tournament.tournament_type == Tournament.TournamentType.AMERICANO:
            p1 = match.participant1.user if match.participant1 else None
            p3 = match.participant4.user if match.participant4 else None # Partner p1
            p2 = match.participant2.user if match.participant2 else None
            p4 = match.participant3.user if match.participant3 else None # Partner p2
        else: # Standardowe parowanie dla singla i debla
            p1 = match.participant1.user if match.participant1 else None
            p2 = match.participant2.user if match.participant2 else None
            p3 = match.participant3.user if match.participant3 else None
            p4 = match.participant4.user if match.participant4 else None

        converted_match = {
            'id': f"t_{match.id}",  # Prefiks 't_' aby uniknąć kolizji ID
            'p1_id': p1.id if p1 else None,
            'p2_id': p2.id if p2 else None,
            'p3_id': p3.id if p3 else None,
            'p4_id': p4.id if p4 else None,
            'p1_set1': match.set1_p1_score or 0, 'p2_set1': match.set1_p2_score or 0,
            'p1_set2': match.set2_p1_score or 0, 'p2_set2': match.set2_p2_score or 0,
            'p1_set3': match.set3_p1_score or 0, 'p2_set3': match.set3_p2_score or 0,
            'match_double': is_double,
            'description': f"Turniej: {match.tournament.name}",
            'match_date': match.scheduled_time.date() if match.scheduled_time else match.tournament.start_date.date(),
            'match_id': match.id, # Dodanie osobnego ID do URL
            'tournament_id': match.tournament.id, # Dodanie ID turnieju do URL
            'is_tournament': True, # Dodatkowa flaga do identyfikacji w szablonach
        }
        converted_matches.append(converted_match)
    
    # 5. Zastosuj filtry dotyczące graczy (friend_id, partner_id, opponent_partner_id)
    # Te filtry są stosowane na liście słowników, ponieważ ich logika zależy od ról graczy
    # w meczu, co jest łatwiejsze do określenia po konwersji.
    final_filtered_matches = []
    uid = user.pk

    for match_dict in converted_matches:
        # Zastosuj filtr friend_id (przeciwnik)
        if filters and filters.get("friend_id"):
            fid = int(filters["friend_id"])
            is_opponent = False
            if match_dict.get("match_double"):
                # Użytkownik jest w drużynie 1 (p1, p3), znajomy jest w drużynie 2 (p2, p4)
                if (uid in [match_dict.get("p1_id"), match_dict.get("p3_id")] and fid in [match_dict.get("p2_id"), match_dict.get("p4_id")]) or \
                   (uid in [match_dict.get("p2_id"), match_dict.get("p4_id")] and fid in [match_dict.get("p1_id"), match_dict.get("p3_id")]):
                    is_opponent = True
            else: # Singiel
                if (uid == match_dict.get("p1_id") and fid == match_dict.get("p2_id")) or \
                   (uid == match_dict.get("p2_id") and fid == match_dict.get("p1_id")):
                    is_opponent = True
            if not is_opponent:
                continue # Pomiń, jeśli znajomy nie jest przeciwnikiem

        # Zastosuj filtr partner_id (partner użytkownika)
        if filters and filters.get("partner_id"):
            pid = int(filters["partner_id"])
            is_partner = False
            if match_dict.get("match_double"):
                if (uid == match_dict.get("p1_id") and pid == match_dict.get("p3_id")) or \
                   (uid == match_dict.get("p3_id") and pid == match_dict.get("p1_id")) or \
                   (uid == match_dict.get("p2_id") and pid == match_dict.get("p4_id")) or \
                   (uid == match_dict.get("p4_id") and pid == match_dict.get("p2_id")):
                    is_partner = True
            if not is_partner:
                continue # Pomiń, jeśli partner nie pasuje do filtra

        # Zastosuj filtr opponent_partner_id (partner przeciwnika)
        if filters and filters.get("opponent_partner_id") and filters.get("friend_id"):
            opid = int(filters["opponent_partner_id"])
            fid = int(filters["friend_id"]) # friend_id musi być obecny, aby ten filtr miał sens
            is_opponent_partner = False
            if match_dict.get("match_double"):
                if (fid == match_dict.get("p1_id") and opid == match_dict.get("p3_id")) or \
                   (fid == match_dict.get("p3_id") and opid == match_dict.get("p1_id")) or \
                   (fid == match_dict.get("p2_id") and opid == match_dict.get("p4_id")) or \
                   (fid == match_dict.get("p4_id") and opid == match_dict.get("p2_id")):
                    is_opponent_partner = True
            if not is_opponent_partner:
                continue # Pomiń, jeśli partner przeciwnika nie pasuje do filtra

        final_filtered_matches.append(match_dict)

    return final_filtered_matches


def get_single_tournament_match_as_friendly(match_id: int):
    """
    Pobiera pojedynczy mecz turniejowy i konwertuje go na obiekt
    podobny do `matches.Match`, aby był kompatybilny z szablonem match_detail.
    """
    try:
        match = TournamentsMatch.objects.select_related(
            'tournament',
            'participant1__user', 'participant2__user',
            'participant3__user', 'participant4__user'
        ).get(id=match_id)
    except TournamentsMatch.DoesNotExist:
        return None

    # Rozpoznaj, czy mecz jest deblowy
    is_double = (
        (match.participant1 and match.participant2 and match.participant3 and match.participant4) or
        match.tournament.match_format == Tournament.MatchFormat.DOUBLES
    )

    # Mapowanie graczy
    if match.tournament.tournament_type == Tournament.TournamentType.AMERICANO:
        p1 = match.participant1.user if match.participant1 else None
        p3 = match.participant4.user if match.participant4 else None
        p2 = match.participant2.user if match.participant2 else None
        p4 = match.participant3.user if match.participant3 else None
    else:
        p1 = match.participant1.user if match.participant1 else None
        p2 = match.participant2.user if match.participant2 else None
        p3 = match.participant3.user if match.participant3 else None
        p4 = match.participant4.user if match.participant4 else None

    # Tworzenie obiektu podobnego do `Match` za pomocą SimpleNamespace
    # To pozwala na dostęp do atrybutów w szablonie za pomocą notacji z kropką (np. match.p1)
    friendly_match = SimpleNamespace(
        id=f"t_{match.id}",
        p1=p1,
        p2=p2,
        p3=p3,
        p4=p4,
        p1_set1=match.set1_p1_score,
        p2_set1=match.set1_p2_score,
        p1_set2=match.set2_p1_score,
        p2_set2=match.set2_p2_score,
        p1_set3=match.set3_p1_score,
        p2_set3=match.set3_p2_score,
        match_double=is_double,
        match_date=match.scheduled_time.date() if match.scheduled_time else match.tournament.start_date.date(),
        description=f"Turniej: {match.tournament.name}",
        is_tournament=True,
        tournament_id=match.tournament.id,
        # Dodajemy metody, których może oczekiwać szablon
        activities=match.activities,
        get_players=lambda: [p for p in [p1, p2, p3, p4] if p is not None]
    )

    return friendly_match


def calculate_americano_standings(tournament):
    """
    Helper function to calculate and return the standings for an Americano tournament.
    """
    participants = tournament.participants.filter(status__in=['ACT', 'REG'])
    matches = tournament.matches.filter(status=TournamentsMatch.Status.COMPLETED.value)

    standings = {
        p.id: {
            'participant': p,
            'points': 0,
            'matches_played': 0,
        } for p in participants
    }

    for match in matches:
        player_ids = [match.participant1_id, match.participant2_id, match.participant3_id, match.participant4_id]
        if not all(pid in standings for pid in player_ids if pid is not None):
            continue

        score1 = match.set1_p1_score or 0
        if match.participant1_id:
            standings[match.participant1_id]['points'] += score1
        if match.participant2_id:
            standings[match.participant2_id]['points'] += score1

        score2 = match.set1_p2_score or 0
        if match.participant3_id:
            standings[match.participant3_id]['points'] += score2
        if match.participant4_id:
            standings[match.participant4_id]['points'] += score2

        for pid in player_ids:
            if pid and pid in standings:
                standings[pid]['matches_played'] += 1

    standings_list = sorted(standings.values(), key=lambda x: x['points'], reverse=True)
    return standings_list


def calculate_round_robin_standings(tournament, participants, config):
    """
    Oblicza tabelę wyników dla turnieju Round Robin.
    """
    standings = {
        p.id: {
            'participant': p,
            'points': Decimal('0.0'),
            'matches_played': 0,
            'wins': 0,
            'losses': 0,
            'sets_won': 0,
            'sets_lost': 0,
            'games_won': 0,
            'games_lost': 0,
        } for p in participants
    }

    matches = tournament.matches.filter(status=TournamentsMatch.Status.COMPLETED.value)

    for match in matches:
        p1_id = match.participant1_id
        p2_id = match.participant2_id
        winner_id = match.winner_id

        if p1_id not in standings or p2_id not in standings:
            continue

        standings[p1_id]['matches_played'] += 1
        standings[p2_id]['matches_played'] += 1

        if winner_id == p1_id:
            standings[p1_id]['wins'] += 1
            standings[p2_id]['losses'] += 1
            standings[p1_id]['points'] += Decimal(config.points_for_win)
            standings[p2_id]['points'] += Decimal(config.points_for_loss)
        elif winner_id == p2_id:
            standings[p2_id]['wins'] += 1
            standings[p1_id]['losses'] += 1
            standings[p2_id]['points'] += config.points_for_win
            standings[p1_id]['points'] += config.points_for_loss

        sets_played = 0
        for i in range(1, 4):
            p1_score = getattr(match, f'set{i}_p1_score', None)
            p2_score = getattr(match, f'set{i}_p2_score', None)
            if p1_score is not None and p2_score is not None:
                is_super_tie_break = (i == 3 and (p1_score >= 10 or p2_score >= 10))
                if is_super_tie_break:
                    standings[p1_id]['points'] += (p1_score * config.points_for_supertiebreak_win)
                    standings[p1_id]['points'] += (p2_score * config.points_for_supertiebreak_loss)
                    standings[p2_id]['points'] += (p2_score * config.points_for_supertiebreak_win)
                    standings[p2_id]['points'] += (p1_score * config.points_for_supertiebreak_loss)
                else:
                    standings[p1_id]['games_won'] += p1_score
                    standings[p2_id]['games_won'] += p2_score
                    standings[p1_id]['games_lost'] += p2_score
                    standings[p2_id]['games_lost'] += p1_score
                    standings[p1_id]['points'] += (p1_score * config.points_for_gem_win)
                    standings[p1_id]['points'] += (p2_score * config.points_for_gem_loss)
                    standings[p2_id]['points'] += (p2_score * config.points_for_gem_win)
                    standings[p2_id]['points'] += (p1_score * config.points_for_gem_loss)

                if p1_score > p2_score:
                    standings[p1_id]['sets_won'] += 1
                    standings[p2_id]['sets_lost'] += 1
                    standings[p1_id]['points'] += Decimal(config.points_for_set_win) if config.points_for_set_win else Decimal('0')
                    standings[p2_id]['points'] += Decimal(config.points_for_set_loss) if config.points_for_set_loss else Decimal('0')
                    sets_played += 1
                elif p2_score > p1_score:
                    standings[p2_id]['sets_won'] += 1
                    standings[p1_id]['sets_lost'] += 1
                    standings[p2_id]['points'] += Decimal(config.points_for_set_win) if config.points_for_set_win else Decimal('0')
                    standings[p1_id]['points'] += Decimal(config.points_for_set_loss) if config.points_for_set_loss else Decimal('0')
                    sets_played += 1

    standings_list = []
    for data in standings.values():
        data['sets_diff'] = data['sets_won'] - data['sets_lost']
        data['games_diff'] = data['games_won'] - data['games_lost']
        standings_list.append(data)

    standings_list.sort(key=lambda x: (x['points'], x['sets_diff'], x['games_diff']), reverse=True)
    return standings_list


def annotate_match_permissions(matches, user, tournament):
    """
    Dodaje atrybuty 'permission' do obiektów meczów, aby ułatwić obsługę w widokach i szablonach.
    """
    if not user.is_authenticated:
        for match in matches:
            match.can_edit = False
            match.can_start = False
            match.user_reaction = None
        return

    # Pobieranie reakcji użytkownika
    if isinstance(matches, list):
         match_ids = [m.id for m in matches]
         queryset_matches = TournamentsMatch.objects.filter(id__in=match_ids)
    else:
        queryset_matches = matches
        
    user_reactions = MatchReaction.objects.filter(
        match__in=queryset_matches,
        user=user
    ).values_list('match_id', 'emoji')
    user_reactions_dict = {match_id: emoji for match_id, emoji in user_reactions}

    is_organizer = user == tournament.created_by
    
    # Obsługa parametru matches jako QuerySet lub listy
    iterable_matches = matches if isinstance(matches, (list, tuple)) else matches

    for match in iterable_matches:
        match.user_reaction = user_reactions_dict.get(match.id)
        
        # Sprawdzenie uczestnictwa w meczu - uwzględnia singiel (p1, p2) i debel/americano (p3, p4)
        is_participant_in_match = False
        participants_users = []
        if match.participant1 and match.participant1.user: participants_users.append(match.participant1.user)
        if match.participant2 and match.participant2.user: participants_users.append(match.participant2.user)
        if match.participant3 and match.participant3.user: participants_users.append(match.participant3.user)
        if match.participant4 and match.participant4.user: participants_users.append(match.participant4.user)
        
        if user in participants_users:
            is_participant_in_match = True

        match.can_start = match.status == TournamentsMatch.Status.SCHEDULED.value

        if is_organizer and tournament.status != Tournament.Status.FINISHED.value:
            # Dla organizatora też sprawdzamy blokadę rund w systemie szwajcarskim/pucharowym
            if tournament.tournament_type in [Tournament.TournamentType.SWISS, Tournament.TournamentType.SINGLE_ELIMINATION]:
                current_max_round = tournament.matches.aggregate(max_r=Max('round_number'))['max_r'] or 1
                match.can_edit = match.round_number == current_max_round
            else:
                match.can_edit = True
        elif is_participant_in_match:
             # Uczestnik może edytować tylko, gdy turniej jest aktywny ORAZ mecz jest w bieżącej (ostatniej) rundzie.
             # Dla systemu szwajcarskiego i pucharowego blokujemy edycję poprzednich rund.
             current_max_round = tournament.matches.aggregate(max_r=Max('round_number'))['max_r'] or 1
             match.can_edit = (tournament.status == Tournament.Status.ACTIVE.value and
                               match.round_number == current_max_round)
        else:
            match.can_edit = False
