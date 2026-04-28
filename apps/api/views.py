import logging
from rest_framework import viewsets, generics, status
from rest_framework.permissions import IsAuthenticatedOrReadOnly, AllowAny, IsAuthenticated

logger = logging.getLogger(__name__)
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.tournaments.models import Tournament
from apps.matches import tools as match_tools
from apps.matches.models import Match
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


class MatchDetailView(generics.RetrieveAPIView):
    """GET /api/matches/<id>/ — szczegóły pojedynczego meczu towarzyskiego.
    Dodaje pole can_edit: true gdy request.user jest uczestnikiem lub is_staff."""
    serializer_class = MatchHistorySerializer
    permission_classes = [IsAuthenticated]
    queryset = Match.objects.select_related('p1', 'p2', 'p3', 'p4').all()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        players = [instance.p1_id, instance.p2_id]
        if instance.p3_id:
            players.append(instance.p3_id)
        if instance.p4_id:
            players.append(instance.p4_id)
        data['can_edit'] = request.user.is_staff or request.user.pk in players
        return Response(data)


class UserListView(generics.ListAPIView):
    """
    Lista użytkowników z filtrowaniem po ?search= i trybem podpowiedzi ?suggest=1.

    ?search=<query> — filtruje po first_name, last_name, username (icontains, OR).
      Bez search lub query < 2 znaki → pusta lista (nie ujawniamy wszystkich).
      Wyniki posortowane relevance-first, limit 20.

    ?suggest=1 — zwraca do 8 ostatnio zarejestrowanych użytkowników (bez filtrowania).
      Używane przez autocomplete jako "startowe sugestie" przy focus na polu search.
    """
    serializer_class = UserDetailsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from django.db.models import Q, Case, When, IntegerField

        # Tryb podpowiedzi — kilka ostatnich userów bez filtrowania
        if self.request.query_params.get('suggest') == '1':
            return User.objects.order_by('-date_joined')[:8]

        q = self.request.query_params.get('search', '').strip()
        if len(q) < 2:
            return User.objects.none()
        return (
            User.objects
            .filter(
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(username__icontains=q)
            )
            .annotate(
                relevance=Case(
                    When(username__iexact=q, then=0),
                    When(username__istartswith=q, then=1),
                    When(first_name__istartswith=q, then=2),
                    When(last_name__istartswith=q, then=2),
                    default=3,
                    output_field=IntegerField(),
                )
            )
            .order_by('relevance', 'last_name', 'first_name')[:20]
        )


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
      - Sortowanie: aktywne (ACT) na górze, potem REG, SCH, FIN/CNC
      - DRF (szkice) są wykluczone domyślnie — widoczne tylko przez /mine/

    Auth: IsAuthenticatedOrReadOnly — odczyt publiczny.
    """
    serializer_class = TournamentListSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        from django.db.models import Case, When, IntegerField
        return (
            Tournament.objects
            .exclude(status='DRF')
            .select_related('created_by', 'facility')
            .prefetch_related('participants')
            .annotate(
                status_order=Case(
                    When(status='ACT', then=0),
                    When(status='REG', then=1),
                    When(status='SCH', then=2),
                    When(status='FIN', then=3),
                    When(status='CNC', then=4),
                    default=9,
                    output_field=IntegerField(),
                )
            )
            .order_by('status_order', '-created_at')
        )


class MyTournamentsView(generics.ListAPIView):
    """
    Turnieje utworzone przez zalogowanego użytkownika.
    GET /api/tournaments/mine/

    Reużywa TournamentListSerializer — ten sam kształt co /list/.
    Auth: IsAuthenticated — prywatny endpoint.
    """
    serializer_class = TournamentListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from django.db.models import Case, When, IntegerField
        return (
            Tournament.objects
            .filter(created_by=self.request.user)
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


class NotificationMarkReadView(APIView):
    """
    PATCH /api/notifications/{pk}/read/
    Oznacza pojedyncze powiadomienie jako przeczytane.
    Tylko właściciel może oznaczyć swoje powiadomienie.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            notif = Notifications.objects.get(pk=pk, user=request.user)
        except Notifications.DoesNotExist:
            return Response({'detail': 'Nie znaleziono.'}, status=status.HTTP_404_NOT_FOUND)
        notif.is_read = True
        notif.save(update_fields=['is_read'])
        return Response({'id': notif.pk, 'is_read': True}, status=status.HTTP_200_OK)


class NotificationMarkAllReadView(APIView):
    """
    POST /api/notifications/read-all/
    Oznacza wszystkie powiadomienia użytkownika jako przeczytane.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated = Notifications.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'marked': updated}, status=status.HTTP_200_OK)


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
    Zapis wyniku meczu przez organizatora.
    PATCH /api/tournaments/{pk}/matches/{match_pk}/score/

    Obsługuje turnieje: RND (Round Robin) oraz SGL (Single Elimination).
    Uprawnienia: zalogowany + (created_by lub is_staff).

    Body (JSON):
      set1_p1, set1_p2  — wyniki 1. seta (wymagane, chyba że walkover=true)
      set2_p1, set2_p2  — wyniki 2. seta (opcjonalne)
      set3_p1, set3_p2  — wyniki 3. seta / super tie-break (opcjonalne)
      scheduled_time    — ISO 8601 datetime lub null (opcjonalne)
      walkover          — true → ustaw WDR, wymaga winner_participant_id
      winner_participant_id — id uczestnika (wymagane gdy walkover=true)
      cancel            — true → ustaw CNC, wyczyść wyniki

    Odpowiedź 200:
      { "match_id", "status", "winner_id", "winner_name", "score" }

    Logika wyznaczania zwycięzcy:
      - liczy wygrane sety per uczestnik
      - jeśli jeden z nich ≥ sets_to_win → winner + status CMP
      - jeśli są wyniki ale brak zwycięzcy → status INP
      - zapisuje MatchScoreHistory

    SGL: po CMP lub WDR wywołuje advance_winner_in_bracket().
    Re-edycja: mecze CMP i WDR mogą być edytowane (cofnięcie / korekta).
    """
    permission_classes = [IsAuthenticated]

    # Typy turniejów obsługiwane przez ten endpoint
    SUPPORTED_TYPES = (
        Tournament.TournamentType.ROUND_ROBIN,
        Tournament.TournamentType.SINGLE_ELIMINATION,
    )

    def patch(self, request, pk, match_pk):
        from apps.tournaments.models import (
            Tournament, TournamentsMatch, RoundRobinConfig, MatchScoreHistory,
        )

        # ── Pobierz turniej i mecz ────────────────────────────────────────────
        try:
            tournament = Tournament.objects.select_related(
                'round_robin_config', 'elimination_config'
            ).get(pk=pk)
        except Tournament.DoesNotExist:
            return Response({'detail': 'Turniej nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        if tournament.tournament_type not in self.SUPPORTED_TYPES:
            return Response(
                {'detail': 'Endpoint obsługuje turnieje Round Robin (RND) i Single Elimination (SGL).'},
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

        # ── Turniej musi być ACT lub FIN — wyniki można edytować tylko w trakcie lub po zakończeniu
        # SCH/DRF/REG: turniej nie wystartował — zapis wyników niedozwolony
        EDITABLE_STATUSES = (
            Tournament.Status.ACTIVE.value,
            Tournament.Status.FINISHED.value,
        )
        if tournament.status not in EDITABLE_STATUSES:
            return Response(
                {'detail': f'Wyniki meczów można edytować tylko gdy turniej jest w toku (ACT) lub zakończony (FIN). Obecny status: {tournament.status}.'},
                status=status.HTTP_409_CONFLICT,
            )

        # ── Tylko CNC blokuje edycję meczu ───────────────────────────────────
        if match.status == TournamentsMatch.Status.CANCELLED.value:
            return Response(
                {'detail': f'Mecz ma status „{match.get_status_display()}" i nie może być edytowany.'},
                status=status.HTTP_409_CONFLICT,
            )

        # ── Walidacja danych wejściowych ─────────────────────────────────────
        data = request.data
        cancel = bool(data.get('cancel', False))
        walkover = bool(data.get('walkover', False))

        # ── Ścieżka anulowania meczu (CNC) ───────────────────────────────────
        if cancel:
            match.set1_p1_score = None
            match.set1_p2_score = None
            match.set2_p1_score = None
            match.set2_p2_score = None
            match.set3_p1_score = None
            match.set3_p2_score = None
            match.winner = None
            match.status = TournamentsMatch.Status.CANCELLED.value
            match.save(update_fields=[
                'set1_p1_score', 'set1_p2_score',
                'set2_p1_score', 'set2_p2_score',
                'set3_p1_score', 'set3_p2_score',
                'winner', 'status',
            ])
            MatchScoreHistory.objects.create(
                match=match,
                updated_by=request.user,
                set1_p1_score=None, set1_p2_score=None,
                set2_p1_score=None, set2_p2_score=None,
                set3_p1_score=None, set3_p2_score=None,
            )
            return Response({
                'match_id': match.pk,
                'status': match.status,
                'winner_id': None,
                'winner_name': None,
                'score': None,
            }, status=status.HTTP_200_OK)

        # ── Ścieżka walkover (WDR) ────────────────────────────────────────────
        if walkover:
            winner_participant_id = data.get('winner_participant_id')
            if not winner_participant_id:
                return Response(
                    {'detail': 'walkover=true wymaga podania winner_participant_id.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                winner_participant_id = int(winner_participant_id)
            except (ValueError, TypeError):
                return Response(
                    {'detail': 'winner_participant_id musi być liczbą całkowitą.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if winner_participant_id not in (
                match.participant1_id,
                match.participant2_id,
            ):
                return Response(
                    {'detail': 'winner_participant_id musi być jednym z uczestników meczu.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            from apps.tournaments.models import Participant
            try:
                winner = Participant.objects.get(pk=winner_participant_id)
            except Participant.DoesNotExist:
                return Response({'detail': 'Uczestnik nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

            # Wyczyść wyniki setów i ustaw WDR
            match.set1_p1_score = None
            match.set1_p2_score = None
            match.set2_p1_score = None
            match.set2_p2_score = None
            match.set3_p1_score = None
            match.set3_p2_score = None
            match.winner = winner
            match.status = TournamentsMatch.Status.WITHDRAWN.value

            # Opcjonalnie scheduled_time
            if 'scheduled_time' in data:
                raw_st = data.get('scheduled_time')
                if raw_st in (None, '', 'null'):
                    match.scheduled_time = None
                else:
                    from django.utils.dateparse import parse_datetime
                    parsed = parse_datetime(str(raw_st))
                    if parsed is None:
                        return Response(
                            {'detail': 'Nieprawidłowy format scheduled_time (oczekiwany ISO 8601).'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    match.scheduled_time = parsed

            wdr_save_fields = [
                'set1_p1_score', 'set1_p2_score',
                'set2_p1_score', 'set2_p2_score',
                'set3_p1_score', 'set3_p2_score',
                'winner', 'status',
            ]
            if 'scheduled_time' in data:
                wdr_save_fields.append('scheduled_time')
            match.save(update_fields=wdr_save_fields)

            MatchScoreHistory.objects.create(
                match=match,
                updated_by=request.user,
                set1_p1_score=None, set1_p2_score=None,
                set2_p1_score=None, set2_p2_score=None,
                set3_p1_score=None, set3_p2_score=None,
            )

            # SGL: awansuj zwycięzcę do następnej rundy
            if tournament.tournament_type == Tournament.TournamentType.SINGLE_ELIMINATION:
                from apps.tournaments.bracket import advance_winner_in_bracket
                advance_winner_in_bracket(match, tournament)

            return Response({
                'match_id': match.pk,
                'status': match.status,
                'winner_id': winner.pk,
                'winner_name': winner.display_name,
                'score': None,
            }, status=status.HTTP_200_OK)

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

        # ── Walidacja gemów per set ───────────────────────────────────────────
        config_for_validation = getattr(tournament, 'round_robin_config', None)
        if config_for_validation is None:
            from apps.tournaments.models import RoundRobinConfig as _RRC
            config_for_validation, _ = _RRC.objects.get_or_create(tournament=tournament)

        gps = config_for_validation.games_per_set   # np. 6
        sts = config_for_validation.sets_to_win      # np. 2
        max_sets = sts * 2 - 1                        # np. 3

        # Sety 1 i 2: standardowy set gemowy (max gps+2 z przewagą, albo gps:gps → tie-break)
        for i in (1, 2):
            s1 = fields[f'set{i}_p1']
            s2 = fields[f'set{i}_p2']
            if s1 is None or s2 is None:
                continue
            hi, lo = max(s1, s2), min(s1, s2)
            # Maksymalna dozwolona wartość: gps+1 (np. 7 przy 6-gemowym secie z tie-breakiem)
            # lub gps+N gdy system "przewaga" — akceptujemy do gps+10 żeby nie ograniczać
            max_gems = gps + 10
            if hi > max_gems:
                return Response(
                    {'detail': f'Set {i}: wynik {hi} przekracza dozwolone max ({max_gems} gemów).'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Zwycięzca seta musi mieć ≥ gps gemów
            if hi < gps:
                return Response(
                    {'detail': f'Set {i}: zwycięzca musi mieć co najmniej {gps} gemów (max({s1}, {s2}) = {hi}).'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Przy remisie gps:gps → OK (tie-break)
            # Przy wygranym gps:x → x musi być ≤ gps-2 lub gps-1 (jeśli 7:5 lub 7:6)
            # Uproszczona reguła: jeśli hi == gps, to lo może być gps (remis, tie-break)
            # jeśli hi > gps, to różnica musi być ≥ 2 LUB hi == gps+1 (np. 7:6 jest OK)
            if hi > gps and (hi - lo) < 2 and hi != gps + 1:
                return Response(
                    {'detail': f'Set {i}: wynik {s1}:{s2} jest nieprawidłowy (za mała przewaga).'},
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

        # ── Opcjonalnie scheduled_time ────────────────────────────────────────
        update_scheduled_time = 'scheduled_time' in data
        if update_scheduled_time:
            raw_st = data.get('scheduled_time')
            if raw_st in (None, '', 'null'):
                match.scheduled_time = None
            else:
                from django.utils.dateparse import parse_datetime
                parsed = parse_datetime(str(raw_st))
                if parsed is None:
                    return Response(
                        {'detail': 'Nieprawidłowy format scheduled_time (oczekiwany ISO 8601).'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                match.scheduled_time = parsed

        # ── Zapisz wynik ─────────────────────────────────────────────────────
        match.set1_p1_score = fields['set1_p1']
        match.set1_p2_score = fields['set1_p2']
        match.set2_p1_score = fields['set2_p1']
        match.set2_p2_score = fields['set2_p2']
        match.set3_p1_score = fields['set3_p1']
        match.set3_p2_score = fields['set3_p2']
        match.winner = winner
        match.status = new_status
        save_fields = [
            'set1_p1_score', 'set1_p2_score',
            'set2_p1_score', 'set2_p2_score',
            'set3_p1_score', 'set3_p2_score',
            'winner', 'status',
        ]
        if update_scheduled_time:
            save_fields.append('scheduled_time')
        match.save(update_fields=save_fields)

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

        # SGL: awansuj zwycięzcę do następnej rundy (tylko gdy mecz zakończony)
        if (
            tournament.tournament_type == Tournament.TournamentType.SINGLE_ELIMINATION
            and match.status == TournamentsMatch.Status.COMPLETED.value
        ):
            from apps.tournaments.bracket import advance_winner_in_bracket
            advance_winner_in_bracket(match, tournament)

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


class TournamentBracketView(APIView):
    """
    Struktura drabinki dla turnieju Single Elimination.
    GET /api/tournaments/{pk}/bracket/

    Auth: IsAuthenticatedOrReadOnly (publiczny odczyt, spójny z pozostałymi detail endpoints).
    Tylko turnieje SGL — dla innych zwraca 404.

    Zwraca listę rund w kolejności od R1 do finału:
    [
      {
        "round": 1,
        "round_label": "Runda 1" | "Ćwierćfinał" | "Półfinał" | "Finał",
        "matches": [
          {
            "id": int,
            "match_index": int,
            "status": "WAI" | "SCH" | "INP" | "CMP" | "WDR" | "CNC",
            "status_display": str,
            "is_bye": bool,
            "is_third_place": bool,
            "participant1": {"id", "display_name", "seed_number", "user_id"} | null,
            "participant2": {"id", "display_name", "seed_number", "user_id"} | null,
            "winner_id": int | null,
            "score": "6:4 7:5" | null,
            "scheduled_time": ISO str | null
          }, ...
        ]
      }, ...
    ]
    """
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, pk):
        try:
            tournament = Tournament.objects.get(pk=pk)
        except Tournament.DoesNotExist:
            return Response({'detail': 'Turniej nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        if tournament.tournament_type != Tournament.TournamentType.SINGLE_ELIMINATION:
            return Response(
                {'detail': 'Endpoint /bracket/ obsługuje tylko turnieje Single Elimination (SGL).'},
                status=status.HTTP_404_NOT_FOUND,
            )

        from apps.tournaments.bracket import build_bracket_data
        bracket = build_bracket_data(tournament)
        return Response(bracket, status=status.HTTP_200_OK)


class EliminationConfigUpdateView(APIView):
    """
    Tworzenie/edycja konfiguracji Single Elimination przez organizatora.
    POST/PATCH /api/tournaments/{pk}/config/sgl/

    Pola: initial_seeding (RANDOM|SEEDING), third_place_match (bool).
    Tworzy EliminationConfig jeśli nie istnieje.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        return self._upsert(request, pk)

    def patch(self, request, pk):
        return self._upsert(request, pk)

    def _upsert(self, request, pk):
        try:
            tournament = Tournament.objects.get(pk=pk)
        except Tournament.DoesNotExist:
            return Response({'detail': 'Turniej nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        if tournament.tournament_type != Tournament.TournamentType.SINGLE_ELIMINATION:
            return Response(
                {'detail': 'Endpoint /config/sgl/ obsługuje tylko turnieje SGL.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not (request.user.is_staff or tournament.created_by == request.user):
            return Response({'detail': 'Brak uprawnień.'}, status=status.HTTP_403_FORBIDDEN)

        from apps.tournaments.models import EliminationConfig
        config, _ = EliminationConfig.objects.get_or_create(
            tournament=tournament,
            defaults={'initial_seeding': 'SEEDING', 'third_place_match': True},
        )

        data = request.data
        if 'initial_seeding' in data:
            seeding = data['initial_seeding']
            if seeding not in ('RANDOM', 'SEEDING'):
                return Response({'detail': 'initial_seeding musi być RANDOM lub SEEDING.'}, status=status.HTTP_400_BAD_REQUEST)
            config.initial_seeding = seeding
        if 'third_place_match' in data:
            config.third_place_match = bool(data['third_place_match'])

        config.save()
        return Response({
            'initial_seeding': config.initial_seeding,
            'third_place_match': config.third_place_match,
        }, status=status.HTTP_200_OK)


class AmericanoConfigUpdateView(APIView):
    """
    Tworzenie/edycja konfiguracji Americano przez organizatora.
    POST/PATCH /api/tournaments/{pk}/config/amr/

    Pola: points_per_match (int >= 1), number_of_rounds (int >= 1).
    scheduling_type zablokowane na STATIC w tym slice'u (DYNAMIC = Mexicano — później).
    Tworzy AmericanoConfig jeśli nie istnieje.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        return self._upsert(request, pk)

    def patch(self, request, pk):
        return self._upsert(request, pk)

    def _upsert(self, request, pk):
        try:
            tournament = Tournament.objects.get(pk=pk)
        except Tournament.DoesNotExist:
            return Response({'detail': 'Turniej nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        if tournament.tournament_type != Tournament.TournamentType.AMERICANO:
            return Response(
                {'detail': 'Endpoint /config/amr/ obsługuje tylko turnieje AMR.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not (request.user.is_staff or tournament.created_by == request.user):
            return Response({'detail': 'Brak uprawnień.'}, status=status.HTTP_403_FORBIDDEN)

        from apps.tournaments.models import AmericanoConfig
        config, _ = AmericanoConfig.objects.get_or_create(
            tournament=tournament,
            defaults={
                'points_per_match': 32,
                'number_of_rounds': 7,
                'scheduling_type': 'STATIC',
            },
        )

        data = request.data
        if 'points_per_match' in data:
            try:
                ppm = int(data['points_per_match'])
            except (TypeError, ValueError):
                return Response({'detail': 'points_per_match musi być liczbą całkowitą.'}, status=status.HTTP_400_BAD_REQUEST)
            if ppm < 1:
                return Response({'detail': 'points_per_match musi wynosić co najmniej 1.'}, status=status.HTTP_400_BAD_REQUEST)
            config.points_per_match = ppm

        if 'number_of_rounds' in data:
            try:
                nor = int(data['number_of_rounds'])
            except (TypeError, ValueError):
                return Response({'detail': 'number_of_rounds musi być liczbą całkowitą.'}, status=status.HTTP_400_BAD_REQUEST)
            if nor < 1:
                return Response({'detail': 'number_of_rounds musi wynosić co najmniej 1.'}, status=status.HTTP_400_BAD_REQUEST)
            config.number_of_rounds = nor

        # scheduling_type zablokowane — obsługujemy tylko STATIC w tym slice'u
        if 'scheduling_type' in data and data['scheduling_type'] != 'STATIC':
            return Response(
                {'detail': 'scheduling_type DYNAMIC (Mexicano) nie jest jeszcze obsługiwany. Zostaw STATIC.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        config.scheduling_type = 'STATIC'

        config.save()
        return Response({
            'points_per_match': config.points_per_match,
            'number_of_rounds': config.number_of_rounds,
            'scheduling_type': config.scheduling_type,
        }, status=status.HTTP_200_OK)


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


class RebuildRankingsView(APIView):
    """
    Ręczny rebuild precomputed rankingów.
    POST /api/admin/rebuild-rankings/

    Uprawnienia: is_staff only.

    Body (JSON, wszystkie opcjonalne):
      match_type — 'SNG' lub 'DBL' (domyślnie: oba)
      season     — rok (liczba) lub pominięty = wszystkie sezony

    Odpowiedź 200:
      { "rebuilt": <liczba wpisów>, "match_type": ..., "season": ... }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_staff:
            return Response(
                {'detail': 'Wymagane uprawnienia is_staff.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        match_type = request.data.get('match_type')
        season_raw = request.data.get('season')

        # Walidacja match_type
        if match_type is not None and match_type not in ('SNG', 'DBL'):
            return Response(
                {'detail': 'match_type musi być "SNG" lub "DBL".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Walidacja season
        season = None
        if season_raw is not None:
            try:
                season = int(season_raw)
            except (ValueError, TypeError):
                return Response(
                    {'detail': 'season musi być liczbą całkowitą.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        logger.info(
            '[rankings] Ręczny rebuild zainicjowany przez %s: match_type=%s, season=%s.',
            request.user.username, match_type or 'all', season or 'all',
        )

        try:
            from apps.rankings.services.ranking_calculator import rebuild_rankings
            count = rebuild_rankings(match_type=match_type, season=season)
        except Exception as exc:
            logger.error('[rankings] Błąd ręcznego rebuild: %s', exc, exc_info=True)
            return Response(
                {'detail': f'Błąd rebuildu: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.info('[rankings] Ręczny rebuild zakończony: %d wpisów.', count)
        return Response({
            'rebuilt': count,
            'match_type': match_type or 'all',
            'season': season or 'all',
        }, status=status.HTTP_200_OK)


class TournamentFinishView(APIView):
    """
    Zakończenie turnieju — ustawia status na FIN.
    POST /api/tournaments/{pk}/finish/

    Uprawnienia: IsAuthenticated + (created_by OR is_staff).

    Guardy (walidacja przed zmianą statusu):
    - Turniej musi istnieć.
    - Status musi być ACT (tylko aktywny turniej można zakończyć).
      Wyjątek: is_staff może też zakończyć turniej w REG/SCH.
    - Żaden mecz nie może mieć statusu INP (w trakcie).
    - Turniej musi mieć end_date — wymagane przez signal do rebuild rankingów.
      Jeśli brak, endpoint ustawia end_date = teraz (automatyczne uzupełnienie).

    Po zapisie:
    - Signal rebuild_rankings_on_tournament_finish odpala rebuild automatycznie.

    Odpowiedź 200:
      { "id", "status", "end_date", "rankings_rebuilt": bool, "warning": str|null }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from apps.tournaments.models import Tournament, TournamentsMatch

        # ── Pobierz turniej ───────────────────────────────────────────────────
        try:
            tournament = Tournament.objects.select_related('created_by').get(pk=pk)
        except Tournament.DoesNotExist:
            return Response({'detail': 'Turniej nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        # ── Uprawnienia ───────────────────────────────────────────────────────
        if not (request.user == tournament.created_by or request.user.is_staff):
            return Response(
                {'detail': 'Brak uprawnień. Wymagane: organizator turnieju lub is_staff.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # ── Guard: nie można zakończyć już zakończonego lub anulowanego ───────
        if tournament.status == Tournament.Status.FINISHED:
            return Response(
                {'detail': 'Turniej jest już zakończony.'},
                status=status.HTTP_409_CONFLICT,
            )
        if tournament.status == Tournament.Status.CANCELLED:
            return Response(
                {'detail': 'Nie można zakończyć anulowanego turnieju.'},
                status=status.HTTP_409_CONFLICT,
            )

        # ── Guard: tylko ACT (lub admin może też REG/SCH) ─────────────────────
        allowed_statuses = [Tournament.Status.ACTIVE]
        if request.user.is_staff:
            allowed_statuses += [Tournament.Status.REGISTRATION, Tournament.Status.SCHEDULED, Tournament.Status.DRAFT]
        if tournament.status not in allowed_statuses:
            return Response(
                {
                    'detail': (
                        f'Turniej ma status „{tournament.get_status_display()}" '
                        f'i nie może być zakończony. Wymagany status: Trwa (ACT).'
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        # ── Policz nierozegrane mecze (INP/WAI/SCH) — soft warning ──────────
        unplayed_statuses = [
            TournamentsMatch.Status.IN_PROGRESS,
            TournamentsMatch.Status.WAITING,
            TournamentsMatch.Status.SCHEDULED,
        ]
        unplayed_count = TournamentsMatch.objects.filter(
            tournament=tournament,
            status__in=unplayed_statuses,
        ).count()

        # ── Uzupełnij end_date jeśli brak (wymagane przez signal rebuild) ─────
        warnings = []
        if unplayed_count > 0:
            noun = 'mecz nie został rozegrany' if unplayed_count == 1 else 'meczów nie zostało rozegranych'
            pronoun = 'jego wynik' if unplayed_count == 1 else 'ich wyniki'
            warnings.append(f'{unplayed_count} {noun} — {pronoun} nie będą liczone do rankingu.')
        end_date_set = False
        if not tournament.end_date:
            tournament.end_date = timezone.now()
            end_date_set = True
            warnings.append('Brak daty zakończenia — ustawiono automatycznie na teraz.')
            logger.info(
                '[finish] Turniej id=%d nie miał end_date — ustawiono %s.',
                tournament.pk, tournament.end_date,
            )
        warning = ' '.join(warnings) if warnings else None

        # ── Zmień status na FIN i zapisz ──────────────────────────────────────
        tournament.status = Tournament.Status.FINISHED
        save_fields = ['status']
        if end_date_set:
            save_fields.append('end_date')
        tournament.save(update_fields=save_fields)

        logger.info(
            '[finish] Turniej "%s" (id=%d) zakończony przez %s.',
            tournament.name, tournament.pk, request.user.username,
        )

        return Response({
            'id': tournament.pk,
            'status': tournament.status,
            'end_date': tournament.end_date.isoformat() if tournament.end_date else None,
            'warning': warning,
            'unplayed_count': unplayed_count,
        }, status=status.HTTP_200_OK)


class TournamentCreateView(APIView):
    """
    Tworzenie nowego turnieju przez zalogowanego użytkownika.
    POST /api/tournaments/create/

    Uprawnienia: IsAuthenticated.

    Body (JSON):
      name             — wymagane, max 200 znaków
      tournament_type  — 'RND' | 'SGL' | 'DBE' | 'LDR' | 'AMR' | 'SWS' (domyślnie RND)
      match_format     — 'SNG' | 'DBL' (domyślnie SNG)
      description      — opcjonalne
      start_date       — ISO 8601 datetime, opcjonalne
      end_date         — ISO 8601 datetime, opcjonalne
      rank             — 1 | 2 | 3 (domyślnie 1)

    Odpowiedź 201:
      { "id", "name", "status", "tournament_type", "match_format", ... }

    Po utworzeniu tworzona jest domyślna konfiguracja (RoundRobinConfig dla RND).
    Status domyślny: DRF (szkic).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from apps.tournaments.models import Tournament, RoundRobinConfig
        from django.utils.dateparse import parse_datetime

        data = request.data

        # ── Walidacja name ────────────────────────────────────────────────────
        name = str(data.get('name', '')).strip()
        if not name:
            return Response({'detail': 'Pole „name" jest wymagane.'}, status=status.HTTP_400_BAD_REQUEST)
        if len(name) > 200:
            return Response({'detail': 'Nazwa turnieju może mieć max 200 znaków.'}, status=status.HTTP_400_BAD_REQUEST)

        # ── Typ turnieju ──────────────────────────────────────────────────────
        valid_types = [c[0] for c in Tournament.TournamentType.choices]
        tournament_type = str(data.get('tournament_type', 'RND')).upper()
        if tournament_type not in valid_types:
            return Response(
                {'detail': f'Nieprawidłowy tournament_type. Dostępne: {", ".join(valid_types)}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Format meczu ──────────────────────────────────────────────────────
        valid_formats = [c[0] for c in Tournament.MatchFormat.choices]
        match_format = str(data.get('match_format', 'SNG')).upper()
        if match_format not in valid_formats:
            return Response(
                {'detail': f'Nieprawidłowy match_format. Dostępne: {", ".join(valid_formats)}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Ranga ─────────────────────────────────────────────────────────────
        try:
            rank = int(data.get('rank', 1))
            if rank not in (1, 2, 3):
                raise ValueError
        except (ValueError, TypeError):
            return Response({'detail': 'rank musi być 1, 2 lub 3.'}, status=status.HTTP_400_BAD_REQUEST)

        # ── Daty (opcjonalne) ─────────────────────────────────────────────────
        start_date = None
        end_date = None
        for field_name, target in (('start_date', 'start'), ('end_date', 'end')):
            raw = data.get(field_name)
            if raw:
                parsed = parse_datetime(str(raw))
                if parsed is None:
                    return Response(
                        {'detail': f'Nieprawidłowy format {field_name} (oczekiwany ISO 8601).'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if target == 'start':
                    start_date = parsed
                else:
                    end_date = parsed

        if start_date and end_date and end_date <= start_date:
            return Response(
                {'detail': 'end_date musi być późniejszy niż start_date.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Utwórz turniej ────────────────────────────────────────────────────
        tournament = Tournament.objects.create(
            name=name,
            description=str(data.get('description', '')).strip(),
            tournament_type=tournament_type,
            match_format=match_format,
            rank=rank,
            start_date=start_date,
            end_date=end_date,
            status=Tournament.Status.DRAFT,
            created_by=request.user,
        )

        # ── Utwórz domyślną konfigurację ─────────────────────────────────────
        if tournament_type == 'RND':
            RoundRobinConfig.objects.create(tournament=tournament)

        logger.info(
            '[create] Turniej "%s" (id=%d, typ=%s) utworzony przez %s.',
            tournament.name, tournament.pk, tournament_type, request.user.username,
        )

        serializer = TournamentListSerializer(tournament)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class TournamentStatusView(APIView):
    """
    Zmiana statusu turnieju przez organizatora.
    PATCH /api/tournaments/{pk}/status/

    Uprawnienia: IsAuthenticated + (created_by OR is_staff).

    Dozwolone przejścia statusów (dla organizatora):
      DRF → REG  (otwórz rejestrację)
      REG → DRF  (cofnij do szkicu — tylko gdy brak uczestników)
      REG → SCH  (zamknij rejestrację)
      SCH → REG  (ponownie otwórz rejestrację)
      SCH → ACT  (rozpocznij turniej)
      ACT → FIN  (zakończ — lepiej używać /finish/ z pełną walidacją)

    is_staff może wykonać dowolne przejście.

    Body: { "status": "REG" }
    Odpowiedź 200: { "id", "status", "status_display" }
    """
    permission_classes = [IsAuthenticated]

    # Dozwolone przejścia dla zwykłego organizatora
    ALLOWED_TRANSITIONS = {
        'DRF': ['REG'],
        'REG': ['DRF', 'SCH'],
        'SCH': ['REG', 'ACT'],
        'ACT': ['FIN'],
        'FIN': [],
        'CNC': [],
    }

    def patch(self, request, pk):
        from apps.tournaments.models import Tournament

        try:
            tournament = Tournament.objects.select_related('created_by').get(pk=pk)
        except Tournament.DoesNotExist:
            return Response({'detail': 'Turniej nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        if not (request.user == tournament.created_by or request.user.is_staff):
            return Response(
                {'detail': 'Brak uprawnień. Wymagane: organizator turnieju lub is_staff.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        new_status = str(request.data.get('status', '')).upper()
        valid_statuses = [c[0] for c in Tournament.Status.choices]
        if new_status not in valid_statuses:
            return Response(
                {'detail': f'Nieprawidłowy status. Dostępne: {", ".join(valid_statuses)}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_status == tournament.status:
            return Response(
                {'detail': f'Turniej już ma status „{tournament.get_status_display()}".'},
                status=status.HTTP_409_CONFLICT,
            )

        # FIN jest zarezerwowane dla /finish/ — ten endpoint nie obsługuje finalizacji
        if new_status == 'FIN':
            return Response(
                {'detail': 'Użyj akcji zakończenia turnieju — endpoint /finish/ obsługuje walidację i rebuild rankingów.'},
                status=status.HTTP_409_CONFLICT,
            )

        # Weryfikacja przejścia (is_staff może wszystko)
        if not request.user.is_staff:
            allowed = self.ALLOWED_TRANSITIONS.get(tournament.status, [])
            if new_status not in allowed:
                return Response(
                    {
                        'detail': (
                            f'Niedozwolone przejście: {tournament.status} → {new_status}. '
                            f'Dozwolone z tego statusu: {allowed or "brak"}.'
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

        # Guard: cofnięcie do DRF tylko gdy brak aktywnych uczestników (WDN nie liczy się)
        if new_status == 'DRF' and tournament.status == 'REG':
            count = tournament.participants.exclude(status='WDN').count()
            if count > 0:
                return Response(
                    {'detail': f'Nie można cofnąć do szkicu — turniej ma {count} aktywnych uczestników.'},
                    status=status.HTTP_409_CONFLICT,
                )

        # REG → SCH: wymaga ≥2 uczestników, auto-generuje mecze (RND lub SGL)
        # Cały blok owinięty w atomic() — albo mecze + status, albo nic.
        if new_status == 'SCH' and tournament.status == 'REG':
            from apps.tournaments.models import Participant as _Participant
            from django.db import transaction as db_transaction
            participants_qs = _Participant.objects.filter(
                tournament=tournament,
                status__in=['REG', 'ACT'],
            )
            participant_count = participants_qs.count()
            if participant_count < 2:
                return Response(
                    {'detail': f'Za mało uczestników ({participant_count}). Wymagane co najmniej 2, aby zamknąć zapisy i wygenerować mecze.'},
                    status=status.HTTP_409_CONFLICT,
                )
            try:
                with db_transaction.atomic():
                    if tournament.tournament_type == 'RND':
                        from apps.tournaments.views import generate_round_robin_matches_initial
                        match_count, gen_message = generate_round_robin_matches_initial(tournament, participants_qs)
                    elif tournament.tournament_type == 'SGL':
                        from apps.tournaments.views import generate_elimination_matches_initial
                        from apps.tournaments.models import EliminationConfig
                        config, _ = EliminationConfig.objects.get_or_create(
                            tournament=tournament,
                            defaults={'initial_seeding': 'SEEDING', 'third_place_match': True},
                        )
                        match_count, gen_message = generate_elimination_matches_initial(tournament, participants_qs, config)
                    elif tournament.tournament_type == 'AMR':
                        from apps.tournaments.bracket import generate_americano_matches_static
                        from apps.tournaments.models import AmericanoConfig
                        config, _ = AmericanoConfig.objects.get_or_create(
                            tournament=tournament,
                            defaults={
                                'points_per_match': 32,
                                'number_of_rounds': 7,
                                'scheduling_type': 'STATIC',
                            },
                        )
                        if config.scheduling_type != 'STATIC':
                            raise ValueError('Tylko tryb STATIC (Americano) jest obsługiwany w tym etapie.')
                        match_count, gen_message = generate_americano_matches_static(tournament, participants_qs, config)
                    else:
                        match_count, gen_message = 0, 'Generowanie meczów pominięte (format nieobsługiwany).'
                    tournament.status = new_status
                    tournament.save(update_fields=['status'])
            except Exception as exc:
                logger.error('[status] Błąd REG→SCH dla turnieju id=%d: %s', tournament.pk, exc)
                return Response(
                    {'detail': f'Błąd generowania meczów: {exc}. Status nie został zmieniony.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            logger.info('[status] Wygenerowano %d meczów (%s), status→SCH dla turnieju id=%d.', match_count, tournament.tournament_type, tournament.pk)

            response_data = {
                'id': tournament.pk,
                'status': tournament.status,
                'status_display': tournament.get_status_display(),
                'matches_generated': match_count,
                'message': gen_message,
            }
            return Response(response_data, status=status.HTTP_200_OK)

        # SCH → REG: usuń wszystkie mecze i ich historię wyników
        if new_status == 'REG' and tournament.status == 'SCH':
            from apps.tournaments.models import TournamentsMatch as _Match, MatchScoreHistory as _MSH
            match_ids = list(_Match.objects.filter(tournament=tournament).values_list('pk', flat=True))
            if match_ids:
                _MSH.objects.filter(match_id__in=match_ids).delete()
                _Match.objects.filter(pk__in=match_ids).delete()
                logger.info('[status] Usunięto %d meczów i ich historię dla turnieju id=%d (SCH→REG).', len(match_ids), tournament.pk)

        old_status = tournament.status
        tournament.status = new_status
        tournament.save(update_fields=['status'])

        logger.info(
            '[status] Turniej "%s" (id=%d): %s → %s przez %s.',
            tournament.name, tournament.pk,
            old_status, new_status, request.user.username,
        )

        response_data = {
            'id': tournament.pk,
            'status': tournament.status,
            'status_display': tournament.get_status_display(),
        }
        if new_status == 'SCH' and tournament.tournament_type == 'RND':
            response_data['matches_generated'] = match_count
            response_data['message'] = gen_message

        return Response(response_data, status=status.HTTP_200_OK)


class GenerateMatchesView(APIView):
    """
    Ręczne generowanie meczów dla turnieju RR.
    POST /api/tournaments/{pk}/generate-matches/

    Uprawnienia: IsAuthenticated + (created_by OR is_staff).
    Guard:
      - Tylko RND.
      - Status musi być REG lub SCH.
      - Jeśli mecze już istnieją → 409 (użyj SCH→REG aby cofnąć i wyczyścić).
    Zwraca: { count, message }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from apps.tournaments.models import Tournament as _T, Participant as _P, TournamentsMatch as _M
        from apps.tournaments.views import generate_round_robin_matches_initial

        try:
            tournament = _T.objects.select_related('created_by').get(pk=pk)
        except _T.DoesNotExist:
            return Response({'detail': 'Turniej nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        if not (request.user == tournament.created_by or request.user.is_staff):
            return Response({'detail': 'Brak uprawnień.'}, status=status.HTTP_403_FORBIDDEN)

        if tournament.tournament_type != 'RND':
            return Response(
                {'detail': 'Generowanie meczów przez ten endpoint jest dostępne tylko dla Round Robin.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if tournament.status not in ('REG', 'SCH'):
            return Response(
                {'detail': f'Turniej musi być w statusie REG lub SCH (aktualny: {tournament.status}).'},
                status=status.HTTP_409_CONFLICT,
            )

        existing = _M.objects.filter(tournament=tournament).count()
        if existing > 0:
            return Response(
                {'detail': f'Turniej ma już {existing} meczów. Cofnij status do REG aby usunąć mecze i wygenerować ponownie.'},
                status=status.HTTP_409_CONFLICT,
            )

        participants_qs = _P.objects.filter(tournament=tournament, status__in=['REG', 'ACT'])
        if participants_qs.count() < 2:
            return Response(
                {'detail': f'Za mało uczestników ({participants_qs.count()}). Wymagane co najmniej 2.'},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            count, message = generate_round_robin_matches_initial(tournament, participants_qs)
        except Exception as exc:
            logger.error('[generate-matches] Błąd dla turnieju id=%d: %s', tournament.pk, exc)
            return Response({'detail': f'Błąd generowania: {exc}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        logger.info('[generate-matches] Wygenerowano %d meczów RR dla turnieju id=%d przez %s.', count, tournament.pk, request.user.username)
        return Response({'count': count, 'message': message}, status=status.HTTP_200_OK)


class TournamentParticipantView(APIView):
    """
    Zarządzanie uczestnikami turnieju przez organizatora.

    POST   /api/tournaments/{pk}/participants/        — dodaj uczestnika
    DELETE /api/tournaments/{pk}/participants/{p_pk}/ — usuń uczestnika

    Uprawnienia: IsAuthenticated + (created_by OR is_staff).

    POST body:
      user_id     — id użytkownika (wymagane)
      display_name — opcjonalne (domyślnie: first_name + last_name)
      seed_number — opcjonalne

    DELETE: ustawia status uczestnika na WDN (wycofany), nie usuwa rekordu.
    Nie usuwa meczów — mecze z tym uczestnikiem pozostają, organizator musi je obsłużyć.

    Ograniczenia:
    - Turniej musi być w statusie DRF lub REG (dodawanie/usuwanie tylko przed startem)
    - is_staff może modyfikować w każdym statusie
    - Uczestnik nie może być dodany dwa razy
    """
    permission_classes = [IsAuthenticated]

    def _get_tournament(self, pk, user):
        from apps.tournaments.models import Tournament
        try:
            t = Tournament.objects.select_related('created_by').get(pk=pk)
        except Tournament.DoesNotExist:
            return None, Response({'detail': 'Turniej nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)
        if not (user == t.created_by or user.is_staff):
            return None, Response(
                {'detail': 'Brak uprawnień. Wymagane: organizator turnieju lub is_staff.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return t, None

    def post(self, request, pk):
        from apps.tournaments.models import Tournament, Participant, TeamMember

        tournament, err = self._get_tournament(pk, request.user)
        if err:
            return err

        # Status guard: tylko DRF/REG (is_staff może więcej)
        if not request.user.is_staff and tournament.status not in ('DRF', 'REG'):
            return Response(
                {'detail': f'Nie można dodawać uczestników gdy turniej ma status „{tournament.get_status_display()}".'},
                status=status.HTTP_409_CONFLICT,
            )

        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'detail': 'Pole „user_id" jest wymagane.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            target_user = User.objects.get(pk=int(user_id))
        except (User.DoesNotExist, ValueError, TypeError):
            return Response({'detail': 'Użytkownik nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        # Opcjonalny partner (debel)
        partner_user = None
        partner_user_id = request.data.get('partner_user_id')
        if partner_user_id:
            try:
                partner_user = User.objects.get(pk=int(partner_user_id))
            except (User.DoesNotExist, ValueError, TypeError):
                return Response({'detail': 'Partner nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)
            if partner_user == target_user:
                return Response({'detail': 'Kapitan i partner muszą być różnymi osobami.'}, status=status.HTTP_400_BAD_REQUEST)

        # Sprawdź duplikat — czy user jest już aktywnym uczestnikiem turnieju
        # jako kapitan (Participant.user) LUB jako partner (TeamMember.user).
        def _is_active_member(user):
            """Zwraca True jeśli user jest aktywnym kapitanem LUB partnerem w turnieju."""
            as_captain = Participant.objects.filter(
                tournament=tournament, user=user,
            ).exclude(status='WDN').exists()
            if as_captain:
                return True
            as_partner = TeamMember.objects.filter(
                participant__tournament=tournament, user=user,
            ).exclude(participant__status='WDN').exists()
            return as_partner

        if _is_active_member(target_user):
            return Response(
                {'detail': f'Użytkownik „{target_user.get_full_name() or target_user.username}" jest już uczestnikiem turnieju.'},
                status=status.HTTP_409_CONFLICT,
            )

        if partner_user and _is_active_member(partner_user):
            return Response(
                {'detail': f'Partner „{partner_user.get_full_name() or partner_user.username}" jest już uczestnikiem turnieju.'},
                status=status.HTTP_409_CONFLICT,
            )

        # Sprawdź limit uczestników (RoundRobinConfig)
        if tournament.tournament_type == 'RND':
            cfg = getattr(tournament, 'round_robin_config', None)
            if cfg:
                active_count = tournament.participants.exclude(status='WDN').count()
                if active_count >= cfg.max_participants:
                    return Response(
                        {'detail': f'Osiągnięto limit uczestników ({cfg.max_participants}).'},
                        status=status.HTTP_409_CONFLICT,
                    )

        display_name = str(request.data.get('display_name', '')).strip()
        if not display_name:
            full = target_user.get_full_name().strip()
            display_name = full if full else target_user.username

        seed_number = request.data.get('seed_number')
        if seed_number is not None:
            try:
                seed_number = int(seed_number)
            except (ValueError, TypeError):
                seed_number = None

        participant = Participant.objects.create(
            tournament=tournament,
            user=target_user,
            display_name=display_name,
            seed_number=seed_number,
            status='REG',
        )

        # Dodaj TeamMember dla kapitana i partnera (debel)
        TeamMember.objects.create(participant=participant, user=target_user)
        partner_name = None
        if partner_user:
            TeamMember.objects.create(participant=participant, user=partner_user)
            partner_name = partner_user.get_full_name().strip() or partner_user.username

        logger.info(
            '[participant] Dodano uczestnika %s (id=%d) do turnieju "%s" (id=%d) przez %s.%s',
            display_name, participant.pk, tournament.name, tournament.pk, request.user.username,
            f' Partner: {partner_name}' if partner_name else '',
        )

        return Response({
            'id': participant.pk,
            'display_name': participant.display_name,
            'seed_number': participant.seed_number,
            'status': participant.status,
            'user_id': target_user.pk,
            'partner_name': partner_name,
        }, status=status.HTTP_201_CREATED)

    def delete(self, request, pk, p_pk):
        from apps.tournaments.models import Tournament, Participant

        tournament, err = self._get_tournament(pk, request.user)
        if err:
            return err

        if not request.user.is_staff and tournament.status not in ('DRF', 'REG', 'SCH'):
            return Response(
                {'detail': f'Nie można usuwać uczestników gdy turniej ma status „{tournament.get_status_display()}".'},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            participant = Participant.objects.get(pk=p_pk, tournament=tournament)
        except Participant.DoesNotExist:
            return Response({'detail': 'Uczestnik nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        if participant.status == 'WDN':
            return Response({'detail': 'Uczestnik jest już wycofany.'}, status=status.HTTP_409_CONFLICT)

        participant.status = 'WDN'
        participant.save(update_fields=['status'])

        logger.info(
            '[participant] Wycofano uczestnika %s (id=%d) z turnieju "%s" (id=%d) przez %s.',
            participant.display_name, participant.pk, tournament.name, tournament.pk, request.user.username,
        )

        return Response({
            'id': participant.pk,
            'status': 'WDN',
            'display_name': participant.display_name,
        }, status=status.HTTP_200_OK)
