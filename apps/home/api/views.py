from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from apps.tournaments.models import Tournament

class DashboardSummaryView(APIView):
    """
    Lekki endpoint dla dashboardu Astro.
    Zwraca dane potrzebne do stat-cards:
      - ranking (pozycja, punkty)
      - ostatni mecz
      - najbliższa rezerwacja
      - liczba nadchodzących turniejów

    Auth: IsAuthenticated (sesja Django lub JWT).
    Gdy brak danych → null (graceful degradation dla frontendu).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        now = timezone.now()

        # ── Ranking ──────────────────────────────────────────────────
        try:
            from apps.rankings.models import PlayerRanking
            ranking = PlayerRanking.objects.filter(user=user, match_type='SNG').first()
            _display_name = (user.get_full_name().strip() or user.username) if user else None
            ranking_data = {
                'position': ranking.position if ranking else None,
                'points': float(ranking.points) if ranking else None,
                'matches_played': ranking.matches_played if ranking else None,
                'matches_won': ranking.matches_won if ranking else None,
                'matches_lost': ranking.matches_lost if ranking else None,
                'win_rate': round(
                    ranking.matches_won / ranking.matches_played * 100
                ) if ranking and ranking.matches_played else None,
                'display_name': _display_name,
            }
        except Exception:
            ranking_data = None

        # ── Ostatni mecz ────────────────────────────────────────────
        try:
            from apps.matches.models import Match
            from django.db.models import Q
            last_match = (
                Match.objects
                .filter(Q(p1=user) | Q(p2=user) | Q(p3=user) | Q(p4=user))
                .order_by('-match_date', '-last_updated')
                .first()
            )
            if last_match:
                # Wyznacz wynik z perspektywy zalogowanego gracza — licz wszystkie sety
                is_p1_side = (last_match.p1 == user or last_match.p3 == user)
                opponent = last_match.p2 if is_p1_side else last_match.p1

                sets_won = sets_lost = 0
                score_parts = []
                for p1s, p2s in [
                    (last_match.p1_set1, last_match.p2_set1),
                    (last_match.p1_set2, last_match.p2_set2),
                    (last_match.p1_set3, last_match.p2_set3),
                ]:
                    if p1s is None or p2s is None:
                        continue
                    my_s  = p1s if is_p1_side else p2s
                    opp_s = p2s if is_p1_side else p1s
                    score_parts.append(f"{my_s}:{opp_s}")
                    if my_s > opp_s:
                        sets_won += 1
                    elif opp_s > my_s:
                        sets_lost += 1

                last_match_data = {
                    'date': last_match.match_date.isoformat(),
                    'opponent': opponent.get_full_name() or opponent.username,
                    'score': ' '.join(score_parts),
                    'won': sets_won > sets_lost,
                    'double': last_match.match_double,
                }
            else:
                last_match_data = None
        except Exception:
            last_match_data = None

        # ── Najbliższa rezerwacja ──────────────────────────────────
        try:
            from apps.courts.models import Reservation
            next_res = (
                Reservation.objects
                .filter(user=user, start_time__gte=now, status__in=['PENDING', 'CONFIRMED'])
                .select_related('court', 'court__facility')
                .order_by('start_time')
                .first()
            )
            if next_res:
                reservation_data = {
                    'date': next_res.start_time.strftime('%d %b, %H:%M'),
                    'end_time': next_res.end_time.strftime('%H:%M'),
                    'court': str(next_res.court) if next_res.court else None,
                    'status': next_res.status,
                }
            else:
                reservation_data = None
        except Exception:
            reservation_data = None

        # ── Nadchodzące turnieje (liczba) ──────────────────────────
        try:
            upcoming_tournaments_count = Tournament.objects.filter(
                status__in=['REG', 'ACT']
            ).count()
        except Exception:
            upcoming_tournaments_count = None

        # ── Activity feed ───────────────────────────────────────────
        activity_events = []
        try:
            from apps.matches.models import Match
            from django.db.models import Q

            def _full_name(u):
                return (u.get_full_name().strip() or u.username) if u else '?'

            # 1. Mecze towarzyskie — ostatnie 10 z wynikiem (posortujemy później)
            friendly_matches = (
                Match.objects
                .filter(Q(p1=user) | Q(p2=user) | Q(p3=user) | Q(p4=user))
                .filter(p1_set1__isnull=False)   # musi mieć przynajmniej 1 set
                .select_related('p1', 'p2')
                .order_by('-last_updated')[:10]
            )
            for m in friendly_matches:
                is_p1 = (m.p1 == user or m.p3 == user)
                opp   = m.p2 if is_p1 else m.p1

                # Licz sety (ta sama logika co tools.py) — nie porównuj tylko set1
                p1_sets_won = 0
                p2_sets_won = 0
                sets = []
                for s1, s2 in [
                    (m.p1_set1, m.p2_set1),
                    (m.p1_set2, m.p2_set2),
                    (m.p1_set3, m.p2_set3),
                ]:
                    if s1 is None or s2 is None:
                        continue
                    sets.append(f"{s1}:{s2}")
                    if s1 > s2:
                        p1_sets_won += 1
                    elif s2 > s1:
                        p2_sets_won += 1

                if p1_sets_won > p2_sets_won:
                    won = is_p1
                elif p2_sets_won > p1_sets_won:
                    won = not is_p1
                else:
                    won = None  # remis

                result_label = 'Wygrana' if won is True else ('Porażka' if won is False else 'Remis')
                activity_events.append({
                    'type': 'match',
                    'timestamp': m.last_updated.isoformat(),
                    'title': result_label + f' vs {_full_name(opp)}',
                    'detail': ('Debel' if m.match_double else 'Singiel') + ' · ' + ', '.join(sets),
                    'href': f'/matches/{m.pk}',
                    'result': 'win' if won is True else ('loss' if won is False else 'neutral'),
                })
        except Exception:
            pass

        try:
            from apps.tournaments.models import TournamentsMatch, Participant
            # 2. Mecze turniejowe zakończone (CMP) — przez Participant zalogowanego usera
            my_participant_ids = list(
                Participant.objects.filter(user=user).values_list('id', flat=True)
            )
            if my_participant_ids:
                t_matches = (
                    TournamentsMatch.objects
                    .filter(
                        status='CMP',
                    )
                    .filter(
                        Q(participant1_id__in=my_participant_ids) |
                        Q(participant2_id__in=my_participant_ids) |
                        Q(participant3_id__in=my_participant_ids) |
                        Q(participant4_id__in=my_participant_ids)
                    )
                    .select_related(
                        'tournament',
                        'participant1__user', 'participant2__user',
                        'participant3__user', 'participant4__user',
                    )
                    .order_by('-tournament__created_at', '-id')[:10]
                )
                for tm in t_matches:
                    # Ustal stronę gracza i wynik
                    my_p_ids = set(my_participant_ids)
                    is_team_a = (
                        (tm.participant1_id in my_p_ids) or
                        (tm.participant4_id in my_p_ids)
                    )
                    g_a = tm.set1_p1_score
                    g_b = tm.set1_p2_score
                    if g_a is not None and g_b is not None:
                        won = g_a > g_b if is_team_a else g_b > g_a
                        score_str = f'{g_a}:{g_b}'
                    else:
                        won = None
                        score_str = None

                    # Skonstruuj nazwę przeciwnika
                    if is_team_a:
                        opp_p = tm.participant2
                        opp_p2 = tm.participant3
                    else:
                        opp_p = tm.participant1
                        opp_p2 = tm.participant4
                    opp_name = _full_name(opp_p.user if opp_p and opp_p.user else None)
                    if opp_p2 and opp_p2.user:
                        opp_name += f' / {_full_name(opp_p2.user)}'

                    result_label = ('Wygrana' if won else 'Porażka') if won is not None else 'Zakończony'
                    detail = f'Turniej: {tm.tournament.name}'
                    if score_str:
                        detail += f' · {score_str}'

                    ts = (
                        tm.scheduled_time.isoformat()
                        if tm.scheduled_time
                        else tm.tournament.created_at.isoformat()
                    )

                    activity_events.append({
                        'type': 'match',
                        'timestamp': ts,
                        'title': f'{result_label} vs {opp_name}',
                        'detail': detail,
                        'href': f'/tournaments/{tm.tournament_id}',
                        'result': 'win' if won else ('loss' if won is False else 'neutral'),
                    })
        except Exception:
            pass

        try:
            from apps.tournaments.models import Participant
            # 3. Dołączenie do turnieju
            joins = (
                Participant.objects
                .filter(user=user)
                .exclude(status='WDN')
                .select_related('tournament')
                .order_by('-created_at')[:10]
            )
            for p in joins:
                activity_events.append({
                    'type': 'tournament_join',
                    'timestamp': p.created_at.isoformat(),
                    'title': f'Dołączyłeś do turnieju {p.tournament.name}',
                    'detail': p.tournament.get_status_display() if hasattr(p.tournament, 'get_status_display') else '',
                    'href': f'/tournaments/{p.tournament_id}',
                    'result': 'neutral',
                })
        except Exception:
            pass

        try:
            from apps.courts.models import Reservation

            def _weekday_pl(dt):
                days = ['poniedziałek', 'wtorek', 'środę', 'czwartek', 'piątek', 'sobotę', 'niedzielę']
                return days[dt.weekday()]

            reservations = (
                Reservation.objects
                .filter(user=user, status__in=['PENDING', 'CONFIRMED'])
                .order_by('-created_at')[:5]
            )
            for r in reservations:
                day = _weekday_pl(r.start_time)
                time_str = r.start_time.strftime('%H:%M')
                court_str = f' ({r.court})' if r.court else ''
                activity_events.append({
                    'type': 'reservation',
                    'timestamp': r.created_at.isoformat(),
                    'title': f'Zarezerwowałeś kort na {day} {time_str}{court_str}',
                    'detail': r.start_time.strftime('%d %b %Y'),
                    'href': '/astro/courts/reservations',
                    'result': 'neutral',
                })
        except Exception:
            pass

        # Posortuj wszystkie eventy malejąco po timestamp, weź 5
        activity_events.sort(key=lambda e: e['timestamp'], reverse=True)
        activity_data = activity_events[:5]

        return Response({
            'ranking': ranking_data,
            'last_match': last_match_data,
            'next_reservation': reservation_data,
            'upcoming_tournaments_count': upcoming_tournaments_count,
            'activity': activity_data,
        })
