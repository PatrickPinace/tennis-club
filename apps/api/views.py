from rest_framework import viewsets, generics, status
from rest_framework.permissions import IsAuthenticatedOrReadOnly, AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.tournaments.models import Tournament
from apps.matches import tools as match_tools
from .serializers import (TournamentSerializer, TournamentListSerializer, TournamentDetailSerializer,
                          RegisterSerializer, UserDetailsSerializer, NotificationSerializer,
                          MatchCreateSerializer, MatchHistorySerializer, PlayerRankingSerializer,
                          RoundRobinStandingSerializer, RoundRobinConfigSerializer,
                          RoundRobinConfigUpdateSerializer)
from django.contrib.auth.models import User
from django.utils import timezone
from chats.models import ChatMessage
from notifications.models import Notifications


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer


class MatchCreateView(generics.CreateAPIView):
    """API endpoint to create a new friendly match."""
    serializer_class = MatchCreateSerializer
    permission_classes = [IsAuthenticated]


class UserListView(generics.ListAPIView):
    """API endpoint that lists all users."""
    queryset = User.objects.all().order_by('username')
    serializer_class = UserDetailsSerializer
    permission_classes = [IsAuthenticated]


class UserDetailsView(APIView):
    """Returns details of the currently logged-in user."""
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        serializer = UserDetailsSerializer(request.user)
        return Response(serializer.data)


class UnreadChatMessagesCountView(APIView):
    """Returns the count of unread chat conversations for the user."""
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        count = ChatMessage.objects.filter(recipient=request.user, is_read=False).values('sender').distinct().count()
        return Response({'unread_count': count}, status=status.HTTP_200_OK)

class TournamentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint, który pozwala na przeglądanie turniejów.
    """
    queryset = Tournament.objects.all().order_by('-created_at')
    serializer_class = TournamentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class TournamentDetailView(generics.RetrieveAPIView):
    """
    Detal turnieju dla frontendu Astro.
    GET /api/tournaments/{id}/detail/

    Zwraca: dane podstawowe, uczestnicy, mecze, standings (RR), config (RR).
    Auth: IsAuthenticatedOrReadOnly — odczyt publiczny.
    """
    serializer_class = TournamentDetailSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return (
            Tournament.objects
            .select_related('created_by', 'facility', 'round_robin_config')
            .prefetch_related('participants', 'matches')
        )


class TournamentListView(generics.ListAPIView):
    """
    Lekka lista turniejów dla frontendu Astro.
    GET /api/tournaments/list/

    Różnica vs TournamentViewSet:
      - Brak pełnej listy uczestników — tylko participant_count
      - Zawiera: rank, created_by_name, facility_name
      - Sortowanie: aktywne (REG/ACT) na górze, potem DRAFT, potem FIN/CNC

    Auth: IsAuthenticatedOrReadOnly — odczyt publiczny.
    """
    serializer_class = TournamentListSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        from django.db.models import Case, When, IntegerField
        return (
            Tournament.objects
            .select_related('created_by', 'facility')
            .prefetch_related('participants')
            .annotate(
                status_order=Case(
                    When(status='ACT', then=0),
                    When(status='REG', then=1),
                    When(status='SCH', then=2),
                    When(status='DRF', then=3),
                    When(status='FIN', then=4),
                    When(status='CNC', then=5),
                    default=9,
                    output_field=IntegerField(),
                )
            )
            .order_by('status_order', '-created_at')
        )


class NotificationListView(generics.ListAPIView):
    """API endpoint that lists notifications for the current user."""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notifications.objects.filter(user=self.request.user)


class MatchHistoryView(generics.ListAPIView):
    """API endpoint that lists match history with calculated results."""
    serializer_class = MatchHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        filters = match_tools.prepare_filters(self.request)
        results_obj = match_tools.Results(self.request, sort="match_date", **filters)
        return results_obj.qs


class MatchFiltersView(APIView):
    """API endpoint to get filter options for match history."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        all_played_opponents = match_tools.get_played_with_players(request)
        doubles_partners = match_tools.get_doubles_partners(request)
        doubles_opponents = match_tools.get_doubles_opponents(request)
        years = match_tools.prepare_years(request)

        return Response({
            'years': years,
            'all_played_opponents': UserDetailsSerializer(all_played_opponents, many=True).data,
            'doubles_partners': UserDetailsSerializer(doubles_partners, many=True).data,
            'doubles_opponents': UserDetailsSerializer(doubles_opponents, many=True).data,
        })


class RankingListView(generics.ListAPIView):
    """
    Lista rankingowa graczy.
    GET /api/rankings/list/?type=SNG&year=2026

    Query params:
      type  — SNG (domyślny) lub DBL
      year  — rok sezonu (liczba) lub "all" dla all-time

    Auth: IsAuthenticatedOrReadOnly — odczyt publiczny, tak jak turnieje.
    """
    serializer_class = PlayerRankingSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        from apps.rankings.models import PlayerRanking
        match_type = self.request.query_params.get('type', 'SNG').upper()
        year_param = self.request.query_params.get('year', None)

        # Normalizuj typ
        if match_type not in ('SNG', 'DBL'):
            match_type = 'SNG'

        # Wyznacz sezon
        if year_param is None or year_param == '':
            # Domyślnie: najnowszy dostępny sezon z danych
            latest = (
                PlayerRanking.objects
                .filter(match_type=match_type)
                .exclude(season=None)
                .order_by('-season')
                .values_list('season', flat=True)
                .first()
            )
            season = latest  # może być None = all-time
        elif year_param.lower() == 'all':
            season = None
        elif year_param.isdigit():
            season = int(year_param)
        else:
            season = None

        return (
            PlayerRanking.objects
            .filter(match_type=match_type, season=season)
            .select_related('user')
            .order_by('position')
        )


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
            ranking_data = {
                'position': ranking.position if ranking else None,
                'points': float(ranking.points) if ranking else None,
                'matches_played': ranking.matches_played if ranking else None,
                'matches_won': ranking.matches_won if ranking else None,
                'matches_lost': ranking.matches_lost if ranking else None,
                'win_rate': round(
                    ranking.matches_won / ranking.matches_played * 100
                ) if ranking and ranking.matches_played else None,
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
                # Wyznacz wynik z perspektywy zalogowanego gracza
                is_p1_side = (last_match.p1 == user or last_match.p3 == user)
                my_s1  = last_match.p1_set1 if is_p1_side else last_match.p2_set1
                opp_s1 = last_match.p2_set1 if is_p1_side else last_match.p1_set1
                my_s2  = last_match.p1_set2 if is_p1_side else last_match.p2_set2
                opp_s2 = last_match.p2_set2 if is_p1_side else last_match.p1_set2

                sets_won  = sum(1 for m, o in [(my_s1, opp_s1), (my_s2, opp_s2)] if m is not None and o is not None and m > o)
                sets_lost = sum(1 for m, o in [(my_s1, opp_s1), (my_s2, opp_s2)] if m is not None and o is not None and m < o)

                opponent = last_match.p2 if last_match.p1 == user else last_match.p1

                score_parts = [f"{my_s1}:{opp_s1}"]
                if my_s2 is not None and opp_s2 is not None:
                    score_parts.append(f"{my_s2}:{opp_s2}")
                if last_match.p1_set3 is not None:
                    my_s3  = last_match.p1_set3 if is_p1_side else last_match.p2_set3
                    opp_s3 = last_match.p2_set3 if is_p1_side else last_match.p1_set3
                    score_parts.append(f"{my_s3}:{opp_s3}")

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

        return Response({
            'ranking': ranking_data,
            'last_match': last_match_data,
            'next_reservation': reservation_data,
            'upcoming_tournaments_count': upcoming_tournaments_count,
        })


class RoundRobinMatchScoreView(APIView):
    """
    Zapis wyniku meczu Round Robin przez organizatora.
    PATCH /api/tournaments/{pk}/matches/{match_pk}/score/

    Uprawnienia: zalogowany + (created_by lub is_staff).
    Tylko turnieje RND. Nie działa na meczach CMP/WDR/CNC.

    Body (JSON):
      set1_p1, set1_p2  — wyniki 1. seta (wymagane)
      set2_p1, set2_p2  — wyniki 2. seta (opcjonalne)
      set3_p1, set3_p2  — wyniki 3. seta / super tie-break (opcjonalne)

    Odpowiedź 200:
      { "match_id", "status", "winner_id", "winner_name", "score" }

    Logika wyznaczania zwycięzcy identyczna jak TournamentsMatchForm.clean():
      - liczy wygrane sety per uczestnik
      - jeśli jeden z nich ≥ sets_to_win → winner + status CMP
      - jeśli są wyniki ale brak zwycięzcy → status INP
      - zapisuje MatchScoreHistory
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, match_pk):
        from apps.tournaments.models import (
            Tournament, TournamentsMatch, RoundRobinConfig, MatchScoreHistory,
        )

        # ── Pobierz turniej i mecz ────────────────────────────────────────────
        try:
            tournament = Tournament.objects.select_related('round_robin_config').get(pk=pk)
        except Tournament.DoesNotExist:
            return Response({'detail': 'Turniej nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        if tournament.tournament_type != Tournament.TournamentType.ROUND_ROBIN:
            return Response(
                {'detail': 'Endpoint obsługuje tylko turnieje Round Robin (RND).'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── Uprawnienia: only organizer or is_staff ───────────────────────────
        if not (request.user == tournament.created_by or request.user.is_staff):
            return Response(
                {'detail': 'Brak uprawnień. Wymagane: organizator turnieju lub is_staff.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            match = TournamentsMatch.objects.select_related(
                'participant1', 'participant2'
            ).get(pk=match_pk, tournament=tournament)
        except TournamentsMatch.DoesNotExist:
            return Response({'detail': 'Mecz nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        # ── Nie edytuj zakończonych / anulowanych ────────────────────────────
        locked = {
            TournamentsMatch.Status.COMPLETED.value,
            TournamentsMatch.Status.WITHDRAWN.value,
            TournamentsMatch.Status.CANCELLED.value,
        }
        if match.status in locked:
            return Response(
                {'detail': f'Mecz ma status „{match.get_status_display()}" i nie może być edytowany.'},
                status=status.HTTP_409_CONFLICT,
            )

        # ── Walidacja danych wejściowych ─────────────────────────────────────
        data = request.data

        def _int_or_none(key):
            v = data.get(key)
            if v is None or v == '':
                return None
            try:
                return int(v)
            except (ValueError, TypeError):
                return 'invalid'

        fields = {
            'set1_p1': _int_or_none('set1_p1'),
            'set1_p2': _int_or_none('set1_p2'),
            'set2_p1': _int_or_none('set2_p1'),
            'set2_p2': _int_or_none('set2_p2'),
            'set3_p1': _int_or_none('set3_p1'),
            'set3_p2': _int_or_none('set3_p2'),
        }

        if 'invalid' in fields.values():
            return Response(
                {'detail': 'Wyniki setów muszą być liczbami całkowitymi lub null.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if fields['set1_p1'] is None or fields['set1_p2'] is None:
            return Response(
                {'detail': 'Wyniki 1. seta (set1_p1, set1_p2) są wymagane.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Wyniki nie mogą być ujemne
        for key, val in fields.items():
            if val is not None and val < 0:
                return Response(
                    {'detail': f'Wynik „{key}" nie może być ujemny.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ── Walidacja super tie-breaka (set 3: min 10 pkt, przewaga ≥ 2) ─────
        s3p1, s3p2 = fields['set3_p1'], fields['set3_p2']
        if s3p1 is not None and s3p2 is not None:
            is_stb = s3p1 >= 10 or s3p2 >= 10
            if is_stb and abs(s3p1 - s3p2) < 2:
                return Response(
                    {'detail': 'Super tie-break wymaga przewagi co najmniej 2 punktów.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ── Wyznacz zwycięzcę (identyczna logika jak TournamentsMatchForm) ───
        config = getattr(tournament, 'round_robin_config', None)
        if config is None:
            from apps.tournaments.models import RoundRobinConfig
            config, _ = RoundRobinConfig.objects.get_or_create(tournament=tournament)

        sets_to_win = config.sets_to_win
        p1_sets = 0
        p2_sets = 0

        for i in range(1, 4):
            s1 = fields[f'set{i}_p1']
            s2 = fields[f'set{i}_p2']
            if s1 is not None and s2 is not None:
                if s1 > s2:
                    p1_sets += 1
                elif s2 > s1:
                    p2_sets += 1

        winner = None
        new_status = TournamentsMatch.Status.IN_PROGRESS.value
        if p1_sets >= sets_to_win:
            winner = match.participant1
            new_status = TournamentsMatch.Status.COMPLETED.value
        elif p2_sets >= sets_to_win:
            winner = match.participant2
            new_status = TournamentsMatch.Status.COMPLETED.value

        # ── Zapisz wynik ─────────────────────────────────────────────────────
        match.set1_p1_score = fields['set1_p1']
        match.set1_p2_score = fields['set1_p2']
        match.set2_p1_score = fields['set2_p1']
        match.set2_p2_score = fields['set2_p2']
        match.set3_p1_score = fields['set3_p1']
        match.set3_p2_score = fields['set3_p2']
        match.winner = winner
        match.status = new_status
        match.save(update_fields=[
            'set1_p1_score', 'set1_p2_score',
            'set2_p1_score', 'set2_p2_score',
            'set3_p1_score', 'set3_p2_score',
            'winner', 'status',
        ])

        MatchScoreHistory.objects.create(
            match=match,
            updated_by=request.user,
            set1_p1_score=match.set1_p1_score,
            set1_p2_score=match.set1_p2_score,
            set2_p1_score=match.set2_p1_score,
            set2_p2_score=match.set2_p2_score,
            set3_p1_score=match.set3_p1_score,
            set3_p2_score=match.set3_p2_score,
        )

        # ── Odpowiedź ────────────────────────────────────────────────────────
        score_parts = []
        for i in range(1, 4):
            s1 = fields[f'set{i}_p1']
            s2 = fields[f'set{i}_p2']
            if s1 is not None and s2 is not None:
                score_parts.append(f'{s1}:{s2}')

        return Response({
            'match_id': match.pk,
            'status': match.status,
            'winner_id': winner.pk if winner else None,
            'winner_name': winner.display_name if winner else None,
            'score': ' '.join(score_parts) if score_parts else None,
        }, status=status.HTTP_200_OK)


class RoundRobinStandingsView(APIView):
    """
    Tabela ligowa dla turnieju Round Robin.
    GET /api/tournaments/{pk}/standings/

    Zwraca posortowaną tabelę uczestników z pełnymi statystykami.
    Działa tylko dla turniejów typu RND — dla innych zwraca 404.

    Auth: IsAuthenticatedOrReadOnly — odczyt publiczny (spójny z TournamentDetailView).

    Obliczenia:
      - Deleguje do calculate_round_robin_standings() z tools.py (single source of truth).
      - Wzbogaca wynik o: draws, win_rate, position.
      - draws = matches_played - wins - losses (mecze z winner=None przy status=CMP).
      - win_rate = wins / matches_played * 100, zaokrąglone do 1 miejsca; null gdy brak meczów.
      - Sortowanie: points DESC → sets_diff DESC → games_diff DESC
        (tie_breaker_priority z config nie jest używany — znany bug, zostawiony celowo).
    """
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, pk):
        # Pobierz turniej — 404 gdy nie istnieje
        try:
            tournament = (
                Tournament.objects
                .select_related('round_robin_config')
                .get(pk=pk)
            )
        except Tournament.DoesNotExist:
            return Response(
                {'detail': 'Turniej nie istnieje.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Tylko Round Robin
        if tournament.tournament_type != Tournament.TournamentType.ROUND_ROBIN:
            return Response(
                {'detail': 'Ten endpoint działa tylko dla turniejów Round Robin (typ RND).'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Konfiguracja — utwórz domyślną gdy brak (spójnie z views.py turnieju)
        from apps.tournaments.models import RoundRobinConfig
        config = getattr(tournament, 'round_robin_config', None)
        if config is None:
            config, _ = RoundRobinConfig.objects.get_or_create(tournament=tournament)

        # Uczestnicy biorący udział w turnieju — wykluczamy wycofanych i wolne losy.
        # Używamy blacklisty zamiast whitelisty, bo baza może zawierać legacy statusy (ACC, FIN itp.)
        participants = tournament.participants.exclude(status__in=['OUT', 'WDN', 'BYE'])

        # Oblicz tabelę (existing logic, single source of truth)
        from apps.tournaments.tools import calculate_round_robin_standings
        raw = calculate_round_robin_standings(tournament, participants, config)

        # Wzbogać o draws, win_rate, position
        result = []
        for position, row in enumerate(raw, start=1):
            mp   = row['matches_played']
            wins = row['wins']
            losses = row['losses']
            draws = mp - wins - losses       # mecze z CMP i winner=None
            win_rate = round(wins / mp * 100, 1) if mp > 0 else None

            result.append({
                'position':       position,
                'participant_id': row['participant'].id,
                'display_name':   row['participant'].display_name,
                'matches_played': mp,
                'wins':           wins,
                'losses':         losses,
                'draws':          draws,
                'sets_won':       row['sets_won'],
                'sets_lost':      row['sets_lost'],
                'sets_diff':      row['sets_diff'],
                'games_won':      row['games_won'],
                'games_lost':     row['games_lost'],
                'games_diff':     row['games_diff'],
                'points':         row['points'],
                'win_rate':       win_rate,
            })

        serializer = RoundRobinStandingSerializer(result, many=True)
        return Response(serializer.data)


class RoundRobinConfigUpdateView(APIView):
    """
    Edycja konfiguracji Round Robin przez organizatora.
    PATCH /api/tournaments/{pk}/config/

    Uprawnienia: IsAuthenticated + (created_by OR is_staff).
    Tylko turnieje RND. Partial update — podaj tylko pola które chcesz zmienić.

    Walidacja:
    - sets_to_win i games_per_set zablokowane gdy status ≠ DRF/REG
    - points_for_win >= points_for_loss
    - max_participants >= 2, sets_to_win >= 1, games_per_set >= 1
    - punkty w zakresie [-100, 100]

    Odpowiedź 200:
      { "config": {...}, "standings": [...] }
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        from apps.tournaments.models import Tournament, RoundRobinConfig
        from apps.tournaments.tools import calculate_round_robin_standings

        # ── Pobierz turniej ───────────────────────────────────────────────────
        try:
            tournament = (
                Tournament.objects
                .select_related('round_robin_config', 'created_by')
                .get(pk=pk)
            )
        except Tournament.DoesNotExist:
            return Response({'detail': 'Turniej nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        if tournament.tournament_type != Tournament.TournamentType.ROUND_ROBIN:
            return Response(
                {'detail': 'Endpoint obsługuje tylko turnieje Round Robin (RND).'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── Uprawnienia ───────────────────────────────────────────────────────
        if not (request.user == tournament.created_by or request.user.is_staff):
            return Response(
                {'detail': 'Brak uprawnień. Wymagane: organizator turnieju lub is_staff.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # ── Pobierz/utwórz config ─────────────────────────────────────────────
        config = getattr(tournament, 'round_robin_config', None)
        if config is None:
            config, _ = RoundRobinConfig.objects.get_or_create(tournament=tournament)

        # ── Waliduj i zapisz (partial=True — PATCH semantics) ─────────────────
        serializer = RoundRobinConfigUpdateSerializer(
            config, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        config.refresh_from_db()

        # ── Zwróć zaktualizowany config + aktualne standings ──────────────────
        participants = tournament.participants.exclude(status__in=['OUT', 'WDN', 'BYE'])
        raw = calculate_round_robin_standings(tournament, participants, config)

        standings_out = []
        for position, row in enumerate(raw, start=1):
            mp   = row['matches_played']
            wins = row['wins']
            losses = row['losses']
            standings_out.append({
                'position':       position,
                'participant_id': row['participant'].id,
                'display_name':   row['participant'].display_name,
                'matches_played': mp,
                'wins':           wins,
                'losses':         losses,
                'draws':          mp - wins - losses,
                'sets_won':       row['sets_won'],
                'sets_lost':      row['sets_lost'],
                'sets_diff':      row['sets_diff'],
                'games_won':      row['games_won'],
                'games_lost':     row['games_lost'],
                'games_diff':     row['games_diff'],
                'points':         row['points'],
                'win_rate':       round(wins / mp * 100, 1) if mp > 0 else None,
            })

        return Response({
            'config': RoundRobinConfigSerializer(config).data,
            'standings': RoundRobinStandingSerializer(standings_out, many=True).data,
        }, status=status.HTTP_200_OK)
