"""
Ranking calculator — precomputed snapshot logic.

Extracted from apps/rankings/views.py (the original "query hell" live calculation).
Produces identical results but runs once and saves to PlayerRanking table.
"""
import datetime
from datetime import timedelta
from decimal import Decimal
from django.db.models import Max, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from apps.tournaments.models import Tournament, TournamentsMatch, Participant, TeamMember
from apps.rankings.models import TournamentRankPoints, PlayerRanking, RankingCalculationInfo


def _build_filters(match_type, season):
    """Return (finished_tournament_filter, completed_match_filter, completed_or_withdrawn_filter) Q objects.

    cm       — tylko mecze zakończone (CMP); używany dla statystyk setów i gemów
    cm_or_wdr — mecze CMP lub walkower (WDR); używany dla liczenia meczów rozegranych
    """
    ft = (
        Q(tournament__status__in=[Tournament.Status.FINISHED.value, Tournament.Status.ACTIVE.value]) &
        Q(tournament__match_format=match_type) &
        Q(tournament__is_ranked=True)
    )
    if season:
        ft &= (
            Q(tournament__end_date__year=season) |
            (Q(tournament__end_date__isnull=True) & Q(tournament__start_date__year=season))
        )
    cm = Q(status=TournamentsMatch.Status.COMPLETED.value)
    cm_or_wdr = Q(status__in=[
        TournamentsMatch.Status.COMPLETED.value,
        TournamentsMatch.Status.WITHDRAWN.value,
    ])
    return ft, cm, cm_or_wdr


def calculate_rankings(match_type='SNG', season=None):
    """
    Calculate Elo-based ranking for all players for a given match_type + season.
    Returns a list of dicts ready to upsert into PlayerRanking.
    """
    ft, cm, cm_or_wdr = _build_filters(match_type, season)

    # 0. Pobierz bonusy za udział dla poszczególnych rang turniejów
    trp_map = {trp.rank: Decimal(str(trp.participation_bonus)) for trp in TournamentRankPoints.objects.all()}

    # 1. Pobierz mecze chronologicznie
    matches = (
        TournamentsMatch.objects
        .filter(ft & cm_or_wdr)
        .select_related(
            'tournament',
            'participant1', 'participant1__user',
            'participant2', 'participant2__user',
            'winner'
        )
        .annotate(
            sort_date=Coalesce('scheduled_time', 'tournament__start_date')
        )
        .order_by('sort_date', 'round_number', 'match_index')
    )

    # 2. Pobierz max_round dla każdego turnieju pucharowego (wykluczając runda=99 w DBE)
    max_rounds = {}
    tournaments_in_matches = set(m.tournament_id for m in matches)
    if tournaments_in_matches:
        max_round_qs = (
            TournamentsMatch.objects
            .filter(tournament_id__in=tournaments_in_matches)
            .exclude(round_number=99)
            .values('tournament_id')
            .annotate(max_round=Max('round_number'))
        )
        for row in max_round_qs:
            max_rounds[row['tournament_id']] = row['max_round']

    # Słownik do cache'owania członków debla dla uczestnika
    participant_members = {}
    all_participants = Participant.objects.filter(tournament_id__in=tournaments_in_matches).prefetch_related('members__user')
    for p in all_participants:
        members = [m.user for m in p.members.all() if m.user]
        if p.user and p.user not in members:
            members.insert(0, p.user)
        participant_members[p.id] = members

    def get_match_multiplier(match):
        if match.tournament.tournament_type not in [Tournament.TournamentType.SINGLE_ELIMINATION.value, Tournament.TournamentType.DOUBLE_ELIMINATION.value]:
            return Decimal('1.0')
        if match.round_number == 99:  # Grand Final
            return Decimal('1.5')
        if match.round_number == 0:   # 3. miejsce
            return Decimal('1.5')
        
        t_max_round = max_rounds.get(match.tournament_id)
        if t_max_round is not None:
            if match.round_number == t_max_round:
                return Decimal('1.5')  # Finał
            elif match.round_number == t_max_round - 1:
                return Decimal('1.25')  # Półfinał
        return Decimal('1.0')

    # Statystyki graczy
    player_stats = {}
    # Słownik do śledzenia turniejów, w których gracz brał udział
    player_tournaments = {}  # user_id -> set of (tournament_id, rank)
    # Słownik do śledzenia turniejów, w których gracz rozegrał przynajmniej jeden ZAKOŃCZONY mecz
    player_completed_match_tournaments = {}  # user_id -> set of (tournament_id, rank)
    # Słownik do śledzenia daty ostatniego meczu gracza
    player_last_match_date = {}  # user_id -> date

    def get_or_init_player(user_id):
        if user_id not in player_stats:
            player_stats[user_id] = {
                'points': Decimal('1000.00'),
                'matches_won': 0,
                'matches_lost': 0,
                'matches_played': 0,
                'sets_won': 0,
                'sets_lost': 0,
                'games_won': 0,
                'games_lost': 0,
            }
        return player_stats[user_id]

    # Obliczenia Elo i statystyk krok po kroku
    for match in matches:
        p1 = match.participant1
        p2 = match.participant2

        if not p1 or not p2:
            continue

        p1_users = participant_members.get(p1.id, [])
        p2_users = participant_members.get(p2.id, [])

        # Pomijamy mecze bez przypisanych użytkowników
        if not p1_users or not p2_users:
            continue

        # Zaakceptuj graczy w statystykach i zapisz ich udział w turnieju oraz datę ostatniego meczu
        match_date = match.sort_date
        if match_date:
            if hasattr(match_date, 'date'):
                match_date = match_date.date()
        for u in p1_users:
            get_or_init_player(u.id)['matches_played'] += 1
            if u.id not in player_tournaments:
                player_tournaments[u.id] = set()
            player_tournaments[u.id].add((match.tournament_id, match.tournament.rank))
            if match_date:
                player_last_match_date[u.id] = match_date
        for u in p2_users:
            get_or_init_player(u.id)['matches_played'] += 1
            if u.id not in player_tournaments:
                player_tournaments[u.id] = set()
            player_tournaments[u.id].add((match.tournament_id, match.tournament.rank))
            if match_date:
                player_last_match_date[u.id] = match_date

        # Ustal wygraną/przegraną
        if match.winner_id == p1.id:
            for u in p1_users:
                get_or_init_player(u.id)['matches_won'] += 1
            for u in p2_users:
                get_or_init_player(u.id)['matches_lost'] += 1
            s1, s2 = Decimal('1'), Decimal('0')
        elif match.winner_id == p2.id:
            for u in p2_users:
                get_or_init_player(u.id)['matches_won'] += 1
            for u in p1_users:
                get_or_init_player(u.id)['matches_lost'] += 1
            s1, s2 = Decimal('0'), Decimal('1')
        else:
            # Remis / Brak rozstrzygnięcia
            s1, s2 = Decimal('0.5'), Decimal('0.5')

        # Statystyki setów i gemów (tylko CMP)
        if match.status == TournamentsMatch.Status.COMPLETED.value:
            for i in range(1, 4):
                s1_score = getattr(match, f'set{i}_p1_score', None)
                s2_score = getattr(match, f'set{i}_p2_score', None)
                if s1_score is not None and s2_score is not None:
                    # Gemy
                    for u in p1_users:
                        stats = get_or_init_player(u.id)
                        stats['games_won'] += s1_score
                        stats['games_lost'] += s2_score
                    for u in p2_users:
                        stats = get_or_init_player(u.id)
                        stats['games_won'] += s2_score
                        stats['games_lost'] += s1_score

                    # Sety
                    if s1_score > s2_score:
                        for u in p1_users:
                            get_or_init_player(u.id)['sets_won'] += 1
                        for u in p2_users:
                            get_or_init_player(u.id)['sets_lost'] += 1
                    elif s2_score > s1_score:
                        for u in p2_users:
                            get_or_init_player(u.id)['sets_won'] += 1
                        for u in p1_users:
                            get_or_init_player(u.id)['sets_lost'] += 1

            # Śledzenie turniejów, w których gracz faktycznie zagrał zakończony mecz
            for u in p1_users:
                if u.id not in player_completed_match_tournaments:
                    player_completed_match_tournaments[u.id] = set()
                player_completed_match_tournaments[u.id].add((match.tournament_id, match.tournament.rank))
            for u in p2_users:
                if u.id not in player_completed_match_tournaments:
                    player_completed_match_tournaments[u.id] = set()
                player_completed_match_tournaments[u.id].add((match.tournament_id, match.tournament.rank))

        # Obliczenie Elo
        # Średni rating zespołu 1 i zespołu 2
        r1 = sum(get_or_init_player(u.id)['points'] for u in p1_users) / len(p1_users)
        r2 = sum(get_or_init_player(u.id)['points'] for u in p2_users) / len(p2_users)

        try:
            power = (r2 - r1) / Decimal('400')
            ten_to_power = Decimal(str(pow(10, float(power))))
        except Exception:
            ten_to_power = Decimal('1')

        e1 = Decimal('1') / (Decimal('1') + ten_to_power)
        e2 = Decimal('1') - e1

        # K-factor
        k_base = Decimal('15')
        if match.tournament.rank == 1:
            k_base = Decimal('50')
        elif match.tournament.rank == 2:
            k_base = Decimal('30')

        k_final = k_base * get_match_multiplier(match)

        diff1 = k_final * (s1 - e1)
        diff2 = k_final * (s2 - e2)

        for u in p1_users:
            stats = get_or_init_player(u.id)
            stats['points'] = (stats['points'] + diff1).quantize(Decimal('0.01'))
        for u in p2_users:
            stats = get_or_init_player(u.id)
            stats['points'] = (stats['points'] + diff2).quantize(Decimal('0.01'))

    # Dodaj bonusy za udział do końcowych punktów
    today = datetime.date.today()
    for user_id, stats in player_stats.items():
        tournaments = player_completed_match_tournaments.get(user_id, set())
        bonus = Decimal('0.00')
        for t_id, rank in tournaments:
            bonus += trp_map.get(rank, Decimal('0.00'))
        stats['points'] = (stats['points'] + bonus).quantize(Decimal('0.01'))

        # Spadek za nieaktywność (inactivity decay) - tylko dla rankingu wszech czasów (season is None)
        if season is None and user_id in player_last_match_date:
            last_match = player_last_match_date[user_id]
            inactive_days = (today - last_match).days
            if inactive_days > 30:
                weeks_inactive = (inactive_days - 30) // 7
                decay_points = Decimal(str(weeks_inactive * 5))
                stats['points'] = max(Decimal('0.00'), stats['points'] - decay_points).quantize(Decimal('0.01'))

    # Konwersja do formatu wynikowego
    results_list = []
    for user_id, stats in player_stats.items():
        results_list.append({
            'user_id': user_id,
            'match_type': match_type,
            'season': season,
            'points': stats['points'],
            'matches_won': stats['matches_won'],
            'matches_lost': stats['matches_lost'],
            'matches_played': stats['matches_played'],
            'sets_won': stats['sets_won'],
            'sets_lost': stats['sets_lost'],
            'games_won': stats['games_won'],
            'games_lost': stats['games_lost'],
        })

    # Sortowanie rankingu
    results_list.sort(key=lambda x: (x['points'], x['matches_won'], x['sets_won']), reverse=True)

    # Ustalanie pozycji (z uwzględnieniem remisów)
    pos = 0
    prev_key = None
    final_results = []
    for i, row in enumerate(results_list):
        key = (row['points'], row['matches_won'], row['sets_won'])
        if key != prev_key:
            pos = i + 1
            prev_key = key
        row['position'] = pos
        final_results.append(row)

    return final_results



def rebuild_rankings(match_type=None, season=None):
    """
    Rebuild precomputed PlayerRanking snapshots.

    If match_type/season are None, rebuilds ALL combinations found in finished tournaments.
    """
    from django.db.models.functions import ExtractYear as EY

    combos = set()

    if match_type and season is not None:
        combos.add((match_type, season))
    elif match_type:
        years_end = (
            Tournament.objects
            .filter(status__in=[Tournament.Status.FINISHED.value, Tournament.Status.ACTIVE.value], end_date__isnull=False, match_format=match_type)
            .annotate(yr=EY('end_date')).values_list('yr', flat=True).distinct()
        )
        years_start = (
            Tournament.objects
            .filter(status__in=[Tournament.Status.FINISHED.value, Tournament.Status.ACTIVE.value], end_date__isnull=True, start_date__isnull=False, match_format=match_type)
            .annotate(yr=EY('start_date')).values_list('yr', flat=True).distinct()
        )
        years = set(years_end) | set(years_start)
        combos.add((match_type, None))  # all-time
        for y in years:
            combos.add((match_type, y))
    else:
        for mt in ('SNG', 'DBL'):
            years_end = (
                Tournament.objects
                .filter(status__in=[Tournament.Status.FINISHED.value, Tournament.Status.ACTIVE.value], end_date__isnull=False, match_format=mt)
                .annotate(yr=EY('end_date')).values_list('yr', flat=True).distinct()
            )
            years_start = (
                Tournament.objects
                .filter(status__in=[Tournament.Status.FINISHED.value, Tournament.Status.ACTIVE.value], end_date__isnull=True, start_date__isnull=False, match_format=mt)
                .annotate(yr=EY('start_date')).values_list('yr', flat=True).distinct()
            )
            years = set(years_end) | set(years_start)
            combos.add((mt, None))
            for y in years:
                combos.add((mt, y))

    total = 0
    for mt, yr in combos:
        rows = calculate_rankings(match_type=mt, season=yr)
        # Usuń stare wpisy dla tej kombinacji — unikamy śmieciowych pozycji
        PlayerRanking.objects.filter(match_type=mt, season=yr).delete()
        PlayerRanking.objects.bulk_create([
            PlayerRanking(
                user_id=row['user_id'],
                match_type=row['match_type'],
                season=row['season'],
                position=row['position'],
                points=row['points'],
                matches_won=row['matches_won'],
                matches_lost=row['matches_lost'],
                matches_played=row['matches_played'],
                sets_won=row['sets_won'],
                sets_lost=row['sets_lost'],
                games_won=row['games_won'],
                games_lost=row['games_lost'],
            )
            for row in rows
        ])
        total += len(rows)

    # Zapisz informacje o aktualizacji
    now = timezone.now()
    RankingCalculationInfo.objects.create(
        last_run=now,
        next_run=now + timedelta(hours=1)
    )

    # Rotacja logów — zachowaj tylko 20 najnowszych wpisów
    keep_count = 20
    newest_ids = list(
        RankingCalculationInfo.objects.order_by('-last_run', '-id')
        .values_list('id', flat=True)[:keep_count]
    )
    if newest_ids:
        RankingCalculationInfo.objects.exclude(id__in=newest_ids).delete()

    return total
