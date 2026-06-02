import logging
from rest_framework import viewsets, generics, status
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.models import User
from django.utils import timezone

from apps.tournaments.models import Tournament
from apps.tournaments.api.serializers import (
    TournamentSerializer, TournamentListSerializer, TournamentDetailSerializer,
    RoundRobinStandingSerializer, RoundRobinConfigSerializer,
    RoundRobinConfigUpdateSerializer
)

logger = logging.getLogger(__name__)


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


class TournamentCheckNameView(APIView):
    """
    Sprawdza czy turniej o podanej nazwie już istnieje.
    GET /api/tournaments/check-name/?name=...

    Odpowiedź: { "exists": bool, "count": int }
    Auth: IsAuthenticated — tylko zalogowani mogą tworzyć turnieje.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        name = request.query_params.get('name', '').strip()
        if not name:
            return Response({'exists': False, 'count': 0})
        count = Tournament.objects.filter(name__iexact=name).count()
        return Response({'exists': count > 0, 'count': count})


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
      - jika jeden z nich ≥ sets_to_win → winner + status CMP
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
        Tournament.TournamentType.DOUBLE_ELIMINATION,
        Tournament.TournamentType.AMERICANO,
        Tournament.TournamentType.LADDER,
    )

    def patch(self, request, pk, match_pk):
        from apps.tournaments.models import (
            Tournament, TournamentsMatch, RoundRobinConfig, MatchScoreHistory,
        )

        # ── Pobierz turniej ───────────────────────────────────────────────────
        try:
            tournament = Tournament.objects.select_related(
                'round_robin_config', 'elimination_config'
            ).get(pk=pk)
        except Tournament.DoesNotExist:
            return Response({'detail': 'Turniej nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        if tournament.tournament_type not in self.SUPPORTED_TYPES:
            return Response(
                {'detail': 'Endpoint obsługuje turnieje Round Robin (RND), Single Elimination (SGL), Americano (AMR) i Ladder (LDR).'},
                status=status.HTTP_404_NOT_FOUND,
            )

        is_organizer = request.user == tournament.created_by or request.user.is_staff

        # ── Pobierz mecz ─────────────────────────────────────────────────────
        try:
            match = TournamentsMatch.objects.select_related(
                'participant1__user', 'participant2__user',
                'participant3__user', 'participant4__user',
            ).get(pk=match_pk, tournament=tournament)
        except TournamentsMatch.DoesNotExist:
            return Response({'detail': 'Mecz nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        # ── Uprawnienia ───────────────────────────────────────────────────────
        # Organizator / staff — pełny dostęp do wszystkich typów turniejów.
        # Uczestnik meczu RR — może wpisać wynik setów oraz WDR (bez CNC).
        # Uczestnik meczu AMR STATIC — może wpisać zwykły wynik (bez WDR/CNC).
        # Uczestnik meczu SGL/DBE — self-reported, trust-first (bez CNC/WDR).
        is_rnd_participant = (
            tournament.tournament_type == Tournament.TournamentType.ROUND_ROBIN
            and match.participant1 is not None
            and match.participant2 is not None
            and request.user in (
                match.participant1.user,
                match.participant2.user,
            )
        )
        is_amr_participant = False
        if tournament.tournament_type == Tournament.TournamentType.AMERICANO:
            from apps.tournaments.models import AmericanoConfig
            amr_cfg = getattr(tournament, '_amr_cfg_cache', None)
            if amr_cfg is None:
                amr_cfg = AmericanoConfig.objects.filter(tournament=tournament).first()
            if amr_cfg is not None:
                amr_users = set()
                for attr in ('participant1', 'participant2', 'participant3', 'participant4'):
                    p = getattr(match, attr, None)
                    if p is not None and p.user is not None:
                        amr_users.add(p.user)
                is_amr_participant = request.user in amr_users
        is_sgl_dbe_participant = (
            tournament.tournament_type in (
                Tournament.TournamentType.SINGLE_ELIMINATION,
                Tournament.TournamentType.DOUBLE_ELIMINATION,
            )
            and match.participant1 is not None
            and match.participant2 is not None
            and request.user in (
                match.participant1.user,
                match.participant2.user,
            )
        )
        if not is_organizer and not is_rnd_participant and not is_amr_participant and not is_sgl_dbe_participant:
            return Response(
                {'detail': 'Brak uprawnień. Wymagane: organizator turnieju, is_staff lub uczestnik meczu.'},
                status=status.HTTP_403_FORBIDDEN,
            )

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

        # Cancel — tylko organizer/staff
        if cancel and not is_organizer:
            return Response(
                {'detail': 'Anulowanie meczu jest dostępne wyłącznie dla organizatora i staff.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        # Walkover — organizer/staff lub uczestnik meczu RR
        if walkover and not is_organizer and not is_rnd_participant:
            return Response(
                {'detail': 'Walkover jest dostępny wyłącznie dla organizatora, staff lub uczestnika meczu (tylko RR).'},
                status=status.HTTP_403_FORBIDDEN,
            )

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

            # SGL/DBE: awansuj zwycięzcę do następnej rundy
            if tournament.tournament_type == Tournament.TournamentType.SINGLE_ELIMINATION:
                from apps.tournaments.bracket import advance_winner_in_bracket
                advance_winner_in_bracket(match, tournament)
            elif tournament.tournament_type == Tournament.TournamentType.DOUBLE_ELIMINATION:
                from apps.tournaments.bracket import advance_dbe_match
                advance_dbe_match(match, tournament)

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

        # ── AMR: osobna logika — gemy zamiast setów tenisowych ──────────────────
        # Americano używa set1_p1/set1_p2 jako łączne gemy zdobyte w meczu.
        # Nie ma setów 2 i 3, nie ma RoundRobinConfig — pomijamy całą walidację RR.
        if tournament.tournament_type == Tournament.TournamentType.AMERICANO:
            g1 = fields['set1_p1']
            g2 = fields['set1_p2']
            from apps.tournaments.models import AmericanoConfig
            try:
                amr_cfg = AmericanoConfig.objects.get(tournament=tournament)
            except AmericanoConfig.DoesNotExist:
                return Response(
                    {'detail': 'Turniej nie ma konfiguracji Americano. Skontaktuj się z organizatorem.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if g1 + g2 != amr_cfg.points_per_match:
                return Response(
                    {'detail': f'Suma gemów ({g1}+{g2}={g1+g2}) musi być równa points_per_match ({amr_cfg.points_per_match}).'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if g1 > g2:
                winner = match.participant1
            elif g2 > g1:
                winner = match.participant2
            else:
                winner = None  # remis gemowy — standings liczą gemy, nie wymagają winnera
            new_status = TournamentsMatch.Status.COMPLETED.value
        else:
            is_elimination = tournament.tournament_type in (
                Tournament.TournamentType.SINGLE_ELIMINATION,
                Tournament.TournamentType.DOUBLE_ELIMINATION,
            )

            is_ladder = tournament.tournament_type == Tournament.TournamentType.LADDER

            if is_elimination or is_ladder:
                # SGL/DBE/LDR: używamy EliminationConfig.sets_to_win (lub default 2);
                # pomijamy walidację gemową (format wynikowy jest swobodny)
                try:
                    from apps.tournaments.models import EliminationConfig as _EC
                    elim_cfg = _EC.objects.get(tournament=tournament)
                    sets_to_win = elim_cfg.sets_to_win
                except Exception:
                    sets_to_win = 2  # bezpieczny default

                # Walidacja tenisowa setów (defence-in-depth — frontend ma własną)
                from apps.matches.tools import validate_tennis_set as _vts
                for _s in (1, 2, 3):
                    _a = fields[f'set{_s}_p1']
                    _b = fields[f'set{_s}_p2']
                    if _a is not None and _b is not None:
                        _err = _vts(_a, _b, _s)
                        if _err:
                            return Response({'detail': _err}, status=status.HTTP_400_BAD_REQUEST)
                    elif (_a is None) != (_b is None):
                        return Response(
                            {'detail': f'Set {_s}: wpisz wynik dla obu stron lub żaden.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
            else:
                # ── Walidacja gemów per set (RND) ─────────────────────────────────
                config_for_validation = getattr(tournament, 'round_robin_config', None)
                if config_for_validation is None:
                    from apps.tournaments.models import RoundRobinConfig as _RRC
                    config_for_validation, _ = _RRC.objects.get_or_create(tournament=tournament)

                gps = config_for_validation.games_per_set   # np. 6
                sets_to_win = config_for_validation.sets_to_win

                # Sety 1 i 2: standardowy set gemowy
                for i in (1, 2):
                    s1 = fields[f'set{i}_p1']
                    s2 = fields[f'set{i}_p2']
                    if s1 is None or s2 is None:
                        continue
                    hi, lo = max(s1, s2), min(s1, s2)
                    max_gems = gps + 10
                    if hi > max_gems:
                        return Response(
                            {'detail': f'Set {i}: wynik {hi} przekracza dozwolone max ({max_gems} gemów).'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    if hi < gps:
                        return Response(
                            {'detail': f'Set {i}: zwycięzca musi mieć co najmniej {gps} gemów (max({s1}, {s2}) = {hi}).'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    if hi > gps and (hi - lo) < 2 and hi != gps + 1:
                        return Response(
                            {'detail': f'Set {i}: wynik {s1}:{s2} jest nieprawidłowy (za mała przewaga).'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                # ── Walidacja super tie-breaka (set 3: min 10 pkt, przewaga ≥ 2) ─
                s3p1, s3p2 = fields['set3_p1'], fields['set3_p2']
                if s3p1 is not None and s3p2 is not None:
                    is_stb = s3p1 >= 10 or s3p2 >= 10
                    if is_stb and abs(s3p1 - s3p2) < 2:
                        return Response(
                            {'detail': 'Super tie-break wymaga przewagi co najmniej 2 punktów.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
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

        # ── Guard re-edycji: downstream lock + organizer force flow ─────────
        # Bazuje na starym statusie meczu (przed save), aby odróżnić 1. submit od re-edit.
        _is_reedit = match.status in (
            TournamentsMatch.Status.COMPLETED.value,
            TournamentsMatch.Status.WITHDRAWN.value,
        )
        if _is_reedit:
            _force = data.get('force') is True  # jawny JSON boolean true
            from apps.tournaments.bracket import is_safe_to_reedit as _is_safe
            _safe, _downstream = _is_safe(match, tournament)
            if not _safe:
                if _downstream and _downstream[0].get('type') == 'ladder':
                    return Response(
                        {
                            'detail': 'Mecze ladder nie mogą być edytowane po zakończeniu.',
                            'code': 'ladder_locked',
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
                # SGL / DBE downstream
                if _force and not is_organizer:
                    return Response(
                        {'detail': 'Force jest dostępny wyłącznie dla organizatora lub staff.'},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                if _force and is_organizer:
                    logger.warning(
                        '[score] FORCE re-edit by user=%s tournament=%d match=%d',
                        request.user.pk, tournament.pk, match.pk,
                    )
                    # kontynuuj — organizer świadomie wymusza korektę
                else:
                    return Response(
                        {
                            'detail': 'Wyniku nie można już bezpiecznie zmienić — kolejny mecz został rozegrany.',
                            'code': 'downstream_locked',
                            'downstream': _downstream,
                            'force_allowed': bool(is_organizer),
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

        # ── Zapisz wynik ─────────────────────────────────────────────────────
        _old_status = match.status  # zapamiętaj przed save — guard antyspam notyfikacji
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

        # SGL/DBE: awansuj zwycięzcę do następnej rundy (tylko gdy mecz zakończony)
        if match.status == TournamentsMatch.Status.COMPLETED.value:
            if tournament.tournament_type == Tournament.TournamentType.SINGLE_ELIMINATION:
                from apps.tournaments.bracket import advance_winner_in_bracket
                advance_winner_in_bracket(match, tournament)
            elif tournament.tournament_type == Tournament.TournamentType.DOUBLE_ELIMINATION:
                from apps.tournaments.bracket import advance_dbe_match
                advance_dbe_match(match, tournament)
            elif tournament.tournament_type == Tournament.TournamentType.LADDER:
                # LDR: zamień seed_number gdy challenger (p1) wygrał; wyczyść ChallengeRejection
                from django.db.models import Q as _Q
                from apps.tournaments.models import ChallengeRejection as _CR
                _winner     = match.winner
                _challenger = match.participant1
                _challenged = match.participant2
                if (_winner and _challenger and _challenged
                        and _winner.id == _challenger.id
                        and _challenger.seed_number is not None
                        and _challenged.seed_number is not None):
                    _challenger.seed_number, _challenged.seed_number = (
                        _challenged.seed_number, _challenger.seed_number
                    )
                    _challenger.save(update_fields=['seed_number'])
                    _challenged.save(update_fields=['seed_number'])
                _CR.objects.filter(
                    _Q(rejecting_participant=_challenger) | _Q(rejecting_participant=_challenged)
                    | _Q(challenger_participant=_challenger) | _Q(challenger_participant=_challenged),
                    tournament=tournament,
                ).delete()

        # ── Notyfikacje o wyniku ─────────────────────────────────────────────
        # Wysyłamy tylko gdy status faktycznie zmienił się na finalny (CMP/WDR).
        # Guard _old_status: re-edit CMP→CMP lub WDR→WDR nie spamuje uczestników.
        # Guard request.user: nie powiadamiamy usera który właśnie wpisał wynik.
        _final_statuses = (
            TournamentsMatch.Status.COMPLETED.value,
            TournamentsMatch.Status.WITHDRAWN.value,
        )
        if match.status in _final_statuses and _old_status != match.status:
            from notifications.helpers import notify
            _score_str = ' '.join(
                f'{fields[f"set{i}_p1"]}:{fields[f"set{i}_p2"]}'
                for i in range(1, 4)
                if fields[f'set{i}_p1'] is not None and fields[f'set{i}_p2'] is not None
            ) or '—'
            _p1 = match.participant1
            _p2 = match.participant2
            _winner_name = winner.display_name if winner else None

            # Zbierz unikalnych userów ze wszystkich slotów (p1–p4).
            # p3/p4 wypełnione tylko przy AMR/MEX deblu — dla singla są None.
            _seen_user_pks: set = set()
            for _slot in (match.participant1, match.participant2,
                          match.participant3, match.participant4):
                if not (_slot and _slot.user):
                    continue
                if _slot.user.pk == request.user.pk:
                    continue
                if _slot.user.pk in _seen_user_pks:
                    continue
                _seen_user_pks.add(_slot.user.pk)
                if match.status == TournamentsMatch.Status.WITHDRAWN.value:
                    _msg = (
                        f'🏆 Walkover w turnieju „{tournament.name}": '
                        f'{_p1.display_name if _p1 else "?"} vs {_p2.display_name if _p2 else "?"}. '
                        f'Wygrał: {_winner_name or "?"}.'
                    )
                    _etype = 'tournament.match.walkover'
                else:
                    _msg = (
                        f'📊 Wpisano wynik meczu w turnieju „{tournament.name}": '
                        f'{_p1.display_name if _p1 else "?"} vs {_p2.display_name if _p2 else "?"} — {_score_str}. '
                        f'Wygrał: {_winner_name or "?"}.'
                    )
                    _etype = 'tournament.match.score_entered'
                notify(_slot.user, _msg, target_url=f'/tournaments/{tournament.pk}', event_type=_etype)

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
      - Sortowanie: delegowane do _sort_standings() z tools.py na podstawie config.tie_breaker_priority
        (HEAD / SETS / GAMES). Wartości zapisane przez stary create.astro były niepoprawne
        (points_sets_games itp.) i wpadały w fallback HEAD — naprawiono po stronie create.astro (2026-05).
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
    Struktura drabinki dla turnieju eliminacyjnego (SGL lub DBE).
    GET /api/tournaments/{pk}/bracket/

    Auth: IsAuthenticatedOrReadOnly (publiczny odczyt).
    Obsługuje SGL i DBE — dla innych typów zwraca 404.

    SGL: zwraca listę rund (flat list):
    [ { "round", "round_label", "matches": [...] }, ... ]

    DBE: zwraca słownik z sekcjami:
    {
      "type": "dbe",
      "winners": [ { "round", "round_label", "matches": [...] }, ... ],
      "losers":  [ ... ],
      "grand_final": { "round": 1, "round_label": "Wielki Finał", "matches": [...] } | null,
    }

    match shape (identyczny dla SGL i DBE):
    {
      "id": int, "match_index": int, "bracket_type": "W"|"L"|"GF",
      "status": str, "status_display": str,
      "is_bye": bool, "is_third_place": bool,
      "participant1": {"id", "display_name", "seed_number", "user_id"} | null,
      "participant2": ...,
      "winner_id": int | null, "score": str | null, "scheduled_time": str | null
    }
    """
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, pk):
        try:
            tournament = Tournament.objects.get(pk=pk)
        except Tournament.DoesNotExist:
            return Response({'detail': 'Turniej nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        if tournament.tournament_type == Tournament.TournamentType.SINGLE_ELIMINATION:
            from apps.tournaments.bracket import build_bracket_data
            bracket = build_bracket_data(tournament)
            return Response(bracket, status=status.HTTP_200_OK)

        if tournament.tournament_type == Tournament.TournamentType.DOUBLE_ELIMINATION:
            from apps.tournaments.bracket import build_dbe_bracket_data
            bracket = build_dbe_bracket_data(tournament)
            return Response(bracket, status=status.HTTP_200_OK)

        return Response(
            {'detail': 'Endpoint /bracket/ obsługuje tylko turnieje SGL i DBE.'},
            status=status.HTTP_404_NOT_FOUND,
        )


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

        if tournament.tournament_type not in (
            Tournament.TournamentType.SINGLE_ELIMINATION,
            Tournament.TournamentType.DOUBLE_ELIMINATION,
        ):
            return Response(
                {'detail': 'Endpoint /config/sgl/ obsługuje tylko turnieje SGL i DBE.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not (request.user.is_staff or tournament.created_by == request.user):
            return Response({'detail': 'Brak uprawnień.'}, status=status.HTTP_403_FORBIDDEN)

        is_dbe = tournament.tournament_type == Tournament.TournamentType.DOUBLE_ELIMINATION
        from apps.tournaments.models import EliminationConfig
        config, _ = EliminationConfig.objects.get_or_create(
            tournament=tournament,
            defaults={'initial_seeding': 'SEEDING', 'third_place_match': False if is_dbe else True},
        )

        data = request.data
        if 'initial_seeding' in data:
            seeding = data['initial_seeding']
            if seeding not in ('RANDOM', 'SEEDING'):
                return Response({'detail': 'initial_seeding must be RANDOM or SEEDING.'}, status=status.HTTP_400_BAD_REQUEST)
            config.initial_seeding = seeding
        if 'third_place_match' in data and not is_dbe:
            config.third_place_match = bool(data['third_place_match'])
        if is_dbe:
            config.third_place_match = False  # DBE nie ma meczu o 3. miejsce

        config.save()
        return Response({
            'initial_seeding': config.initial_seeding,
            'third_place_match': config.third_place_match,
        }, status=status.HTTP_200_OK)


class AmericanoConfigUpdateView(APIView):
    """
    Tworzenie/edycja konfiguracji Americano przez organizatora.
    POST/PATCH /api/tournaments/{pk}/config/amr/

    Pola: points_per_match (int >= 1), number_of_rounds (int >= 1),
    scheduling_type ('STATIC' = Americano, 'DYNAMIC' = Mexicano).
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
                return Response({'detail': 'points_per_match must be integer.'}, status=status.HTTP_400_BAD_REQUEST)
            if ppm < 1:
                return Response({'detail': 'points_per_match must be >= 1.'}, status=status.HTTP_400_BAD_REQUEST)
            config.points_per_match = ppm

        if 'number_of_rounds' in data:
            try:
                nor = int(data['number_of_rounds'])
            except (TypeError, ValueError):
                return Response({'detail': 'number_of_rounds must be integer.'}, status=status.HTTP_400_BAD_REQUEST)
            if nor < 1:
                return Response({'detail': 'number_of_rounds must be >= 1.'}, status=status.HTTP_400_BAD_REQUEST)
            config.number_of_rounds = nor

        if 'scheduling_type' in data:
            valid = [c[0] for c in AmericanoConfig.SCHEDULING_CHOICES]
            if data['scheduling_type'] not in valid:
                return Response(
                    {'detail': f'scheduling_type must be in: {valid}.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            config.scheduling_type = data['scheduling_type']

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


class AmrNextRoundView(APIView):
    """
    Manualny fallback generowania następnej rundy Mexicano.
    POST /api/tournaments/{pk}/amr/next-round/

    Guardy:
    - Turniej musi być AMR + DYNAMIC + ACT
    - Bieżąca runda musi być kompletna (wszystkie mecze CMP)
    - Nie przekroczono number_of_rounds
    Uprawnienia: organizator lub is_staff.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from apps.tournaments.models import Tournament, TournamentsMatch, AmericanoConfig
        from apps.tournaments.views import generate_next_mexicano_round, calculate_americano_standings

        try:
            tournament = Tournament.objects.select_related('created_by').get(pk=pk)
        except Tournament.DoesNotExist:
            return Response({'detail': 'Turniej nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        if not (request.user == tournament.created_by or request.user.is_staff):
            return Response({'detail': 'Brak uprawnień.'}, status=status.HTTP_403_FORBIDDEN)

        if tournament.tournament_type != Tournament.TournamentType.AMERICANO:
            return Response({'detail': 'Endpoint tylko dla turnieju AMR.'}, status=status.HTTP_400_BAD_REQUEST)

        config = getattr(tournament, 'americano_config', None)
        if not config or config.scheduling_type != 'DYNAMIC':
            return Response({'detail': 'Endpoint tylko dla trybu DYNAMIC (Mexicano).'}, status=status.HTTP_400_BAD_REQUEST)

        if tournament.status != Tournament.Status.ACTIVE:
            return Response({'detail': 'Turniej musi być aktywny (ACT).'}, status=status.HTTP_409_CONFLICT)

        from django.db.models import Max as _Max
        current_max_round = tournament.matches.aggregate(
            max_round=_Max('round_number')
        ).get('max_round') or 0

        if current_max_round == 0:
            return Response({'detail': 'Brak meczów — wygeneruj pierwszą rundę przez zmianę statusu.'}, status=status.HTTP_409_CONFLICT)

        pending = TournamentsMatch.objects.filter(
            tournament=tournament,
            round_number=current_max_round,
        ).exclude(status__in=[
            TournamentsMatch.Status.COMPLETED.value,
            TournamentsMatch.Status.WITHDRAWN.value,
        ]).exists()

        if pending:
            return Response(
                {'detail': f'Runda {current_max_round} nie jest jeszcze kompletna — nie wszystkie mecze mają status CMP lub WDR.'},
                status=status.HTTP_409_CONFLICT,
            )

        standings_list = calculate_americano_standings(tournament)
        count, message = generate_next_mexicano_round(tournament, config, standings_list)

        if count == 0:
            return Response({'detail': message}, status=status.HTTP_409_CONFLICT)

        return Response({'generated': count, 'message': message}, status=status.HTTP_200_OK)


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

        # ── is_ranked (domyślnie True; False = turniej towarzyski bez wpływu na ranking) ──
        is_ranked = bool(data.get('is_ranked', True))

        # ── Utwórz turniej ────────────────────────────────────────────────────
        tournament = Tournament.objects.create(
            name=name,
            description=str(data.get('description', '')).strip(),
            tournament_type=tournament_type,
            match_format=match_format,
            rank=rank,
            is_ranked=is_ranked,
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
        'DRF': ['REG', 'CNC'],
        'REG': ['DRF', 'SCH', 'CNC'],
        'SCH': ['REG', 'ACT', 'CNC'],
        'ACT': ['FIN', 'CNC'],
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
                    elif tournament.tournament_type == 'DBE':
                        from apps.tournaments.views import generate_elimination_matches_initial
                        from apps.tournaments.models import EliminationConfig, TournamentsMatch as _TM
                        config, _ = EliminationConfig.objects.get_or_create(
                            tournament=tournament,
                            defaults={'initial_seeding': 'SEEDING', 'third_place_match': False},
                        )
                        match_count, gen_message = generate_elimination_matches_initial(
                            tournament, participants_qs, config,
                            bracket_type=_TM.BracketType.WINNERS,
                        )
                    elif tournament.tournament_type == 'AMR':
                        from apps.tournaments.models import AmericanoConfig
                        config, _ = AmericanoConfig.objects.get_or_create(
                            tournament=tournament,
                            defaults={
                                'points_per_match': 32,
                                'number_of_rounds': 7,
                                'scheduling_type': 'STATIC',
                            },
                        )
                        if config.scheduling_type == 'DYNAMIC':
                            # MEX DYNAMIC: generuj tylko rundę 1; kolejne rundy przez AmrNextRoundView
                            from apps.tournaments.views import generate_next_mexicano_round
                            standings_list = [{'participant': p} for p in participants_qs.order_by('pk')]
                            match_count, gen_message = generate_next_mexicano_round(tournament, config, standings_list)
                            if match_count == 0:
                                raise ValueError(gen_message)
                        else:
                            # AMR STATIC: generuj cały harmonogram z góry
                            from apps.tournaments.bracket import generate_americano_matches_static
                            match_count, gen_message = generate_americano_matches_static(tournament, participants_qs, config)
                    elif tournament.tournament_type == 'LDR':
                        # LDR: brak bracketów — tylko przypisanie pozycji startowych (seed_number)
                        from apps.tournaments.models import LadderConfig as _LdrCfg
                        import random as _random
                        ldr_cfg, _ = _LdrCfg.objects.get_or_create(
                            tournament=tournament,
                            defaults={'challenge_range': 3, 'initial_seeding': 'SEEDING'},
                        )
                        participants_list = list(participants_qs.order_by('pk'))
                        if ldr_cfg.initial_seeding == 'RANDOM':
                            _random.shuffle(participants_list)
                        # Przypisz seed_number 1..N tylko tym co jeszcze go nie mają
                        # (jeśli organizer już ręcznie ustawił seedy, respektujemy je — sortujemy po istniejącym seed_number)
                        already_seeded   = [p for p in participants_list if p.seed_number is not None]
                        not_yet_seeded   = [p for p in participants_list if p.seed_number is None]
                        if not already_seeded:
                            # nikt nie ma seedu — przypisz wszystkich
                            for i, p in enumerate(participants_list, start=1):
                                p.seed_number = i
                                p.save(update_fields=['seed_number'])
                        elif not_yet_seeded:
                            # część ma seedy — uzupełnij brakujące kolejnymi wolnymi numerami
                            used = {p.seed_number for p in already_seeded}
                            free = [n for n in range(1, len(participants_list) + 1) if n not in used]
                            for p, num in zip(not_yet_seeded, free):
                                p.seed_number = num
                                p.save(update_fields=['seed_number'])
                        match_count, gen_message = 0, f'Przypisano pozycje startowe dla {len(participants_list)} uczestników.'
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

        # Notyfikacje do uczestników przy ważnych przejściach statusu
        _notify_statuses = {'ACT', 'FIN', 'CNC'}
        if new_status in _notify_statuses:
            from notifications.helpers import notify
            from apps.tournaments.models import Participant as _P
            _msgs = {
                'ACT': f'🎾 Turniej „{tournament.name}" został rozpoczęty. Czas grać!',
                'FIN': f'🏁 Turniej „{tournament.name}" został zakończony.',
                'CNC': f'❌ Turniej „{tournament.name}" został anulowany.',
            }
            _etypes = {
                'ACT': 'tournament.started',
                'FIN': 'tournament.finished',
                'CNC': 'tournament.cancelled',
            }
            _msg = _msgs[new_status]
            _etype = _etypes[new_status]
            _participants = (
                _P.objects.filter(tournament=tournament, status__in=['ACT', 'REG'])
                .select_related('user')
                .exclude(user=None)
            )
            for _p in _participants:
                # Nie notyfikuj organizatora o własnej akcji
                if _p.user and _p.user.pk != request.user.pk:
                    notify(_p.user, _msg, target_url=f'/tournaments/{tournament.pk}', event_type=_etype)

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

        # Reaktywuj WDN jeśli user był już wcześniej uczestnikiem
        existing_wdn = Participant.objects.filter(
            tournament=tournament, user=target_user, status='WDN',
        ).first()

        partner_name = None
        if existing_wdn:
            existing_wdn.display_name = display_name
            existing_wdn.seed_number = seed_number
            existing_wdn.status = 'REG'
            existing_wdn.save(update_fields=['display_name', 'seed_number', 'status'])
            participant = existing_wdn
            # Upewnij się, że TeamMember kapitana istnieje (mógł nie być usunięty, ale dla pewności)
            TeamMember.objects.get_or_create(participant=participant, user=target_user)
            if partner_user:
                TeamMember.objects.get_or_create(participant=participant, user=partner_user)
                partner_name = partner_user.get_full_name().strip() or partner_user.username
        else:
            participant = Participant.objects.create(
                tournament=tournament,
                user=target_user,
                display_name=display_name,
                seed_number=seed_number,
                status='REG',
            )
            # Dodaj TeamMember dla kapitana i partnera (debel)
            TeamMember.objects.create(participant=participant, user=target_user)
            if partner_user:
                TeamMember.objects.create(participant=participant, user=partner_user)
                partner_name = partner_user.get_full_name().strip() or partner_user.username

        logger.info(
            '[participant] Dodano uczestnika %s (id=%d) do turnieju "%s" (id=%d) przez %s.%s',
            display_name, participant.pk, tournament.name, tournament.pk, request.user.username,
            f' Partner: {partner_name}' if partner_name else '',
        )

        # Notyfikuj dodanego uczestnika (nie notyfikuj gdy organizator dodaje siebie)
        if target_user and target_user.pk != request.user.pk:
            from notifications.helpers import notify
            notify(
                target_user,
                f'🎾 Dodano Cię do turnieju „{tournament.name}".',
                target_url=f'/tournaments/{tournament.pk}',
                event_type='tournament.participant.added',
            )
        # Notyfikuj partnera (debel) — jeśli istnieje i jest inną osobą
        if partner_user and partner_user.pk != request.user.pk and partner_user.pk != target_user.pk:
            from notifications.helpers import notify
            notify(
                partner_user,
                f'🎾 Dodano Cię do turnieju „{tournament.name}".',
                target_url=f'/tournaments/{tournament.pk}',
                event_type='tournament.participant.added',
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


class TournamentJoinView(APIView):
    """
    POST /api/tournaments/{pk}/join/

    Zalogowany użytkownik zapisuje siebie do turnieju.
    Reuse logiki z TournamentParticipantView (duplikat, WDN reaktywacja, limit miejsc).

    Warunki:
    - turniej musi być w statusie REG
    - user nie może być już aktywnym uczestnikiem (Participant lub TeamMember)
    - jeśli był WDN → reaktywacja rekordu
    - jeśli osiągniętą max_participants (RND) → 409
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from apps.tournaments.models import Tournament, Participant, TeamMember

        try:
            tournament = Tournament.objects.select_related(
                'created_by', 'round_robin_config'
            ).get(pk=pk)
        except Tournament.DoesNotExist:
            return Response({'detail': 'Turniej nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        if tournament.status != 'REG':
            return Response(
                {'detail': f'Zapisy są zamknięte. Turniej ma status „{tournament.get_status_display()}".'},
                status=status.HTTP_409_CONFLICT,
            )

        user = request.user

        # Sprawdź duplikat
        as_captain = Participant.objects.filter(
            tournament=tournament, user=user,
        ).exclude(status='WDN').exists()
        as_partner = TeamMember.objects.filter(
            participant__tournament=tournament, user=user,
        ).exclude(participant__status='WDN').exists()

        if as_captain or as_partner:
            return Response(
                {'detail': 'Jesteś już zapisany do tego turnieju.'},
                status=status.HTTP_409_CONFLICT,
            )

        # Sprawdź limit (RND)
        if tournament.tournament_type == 'RND':
            cfg = getattr(tournament, 'round_robin_config', None)
            if cfg:
                active_count = tournament.participants.exclude(status='WDN').count()
                if active_count >= cfg.max_participants:
                    return Response(
                        {'detail': f'Osiągnięto limit uczestników ({cfg.max_participants}).'},
                        status=status.HTTP_409_CONFLICT,
                    )

        full = user.get_full_name().strip()
        display_name = full if full else user.username

        # Reaktywuj WDN lub utwórz nowy rekord
        existing_wdn = Participant.objects.filter(
            tournament=tournament, user=user, status='WDN',
        ).first()

        if existing_wdn:
            existing_wdn.display_name = display_name
            existing_wdn.status = 'REG'
            existing_wdn.save(update_fields=['display_name', 'status'])
            participant = existing_wdn
            TeamMember.objects.get_or_create(participant=participant, user=user)
        else:
            participant = Participant.objects.create(
                tournament=tournament,
                user=user,
                display_name=display_name,
                status='REG',
            )
            TeamMember.objects.create(participant=participant, user=user)

        logger.info(
            '[join] Użytkownik %s zapisał się do turnieju "%s" (id=%d).',
            user.username, tournament.name, tournament.pk,
        )

        # Powiadom organizatora (guard: nie notyfikuj gdy organizator zapisuje siebie)
        organizer = tournament.created_by
        if organizer and organizer.pk != user.pk:
            from notifications.helpers import notify
            _display = user.get_full_name().strip() or user.username
            notify(
                organizer,
                f'🎾 {_display} zapisał się do turnieju „{tournament.name}".',
                target_url=f'/tournaments/{tournament.pk}',
                event_type='tournament.participant.joined',
            )

        return Response({
            'id': participant.pk,
            'display_name': participant.display_name,
            'status': participant.status,
        }, status=status.HTTP_201_CREATED)


class LadderConfigUpdateView(APIView):
    """
    Tworzenie/edycja konfiguracji Drabinki Liderów przez organizatora.
    POST/PATCH /api/tournaments/{pk}/config/ldr/

    Pola:
      challenge_range  — int ≥ 1 (ile pozycji w górę gracz może wyzwać)
      initial_seeding  — 'RANDOM' | 'SEEDING'

    Tworzy LadderConfig jeśli nie istnieje. Partial update (PATCH semantics).
    Auth: IsAuthenticated + (created_by OR is_staff).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        return self._upsert(request, pk)

    def patch(self, request, pk):
        return self._upsert(request, pk)

    def _upsert(self, request, pk):
        from apps.tournaments.models import Tournament, LadderConfig

        try:
            tournament = Tournament.objects.select_related('created_by').get(pk=pk)
        except Tournament.DoesNotExist:
            return Response({'detail': 'Turniej nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        if tournament.tournament_type != Tournament.TournamentType.LADDER:
            return Response(
                {'detail': 'Endpoint /config/ldr/ obsługuje tylko turnieje LDR.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not (request.user.is_staff or tournament.created_by == request.user):
            return Response({'detail': 'Brak uprawnień.'}, status=status.HTTP_403_FORBIDDEN)

        config, _ = LadderConfig.objects.get_or_create(
            tournament=tournament,
            defaults={'challenge_range': 3, 'initial_seeding': 'SEEDING'},
        )

        data = request.data

        if 'challenge_range' in data:
            try:
                cr = int(data['challenge_range'])
            except (TypeError, ValueError):
                return Response({'detail': 'challenge_range musi być liczbą całkowitą.'}, status=status.HTTP_400_BAD_REQUEST)
            if cr < 1:
                return Response({'detail': 'challenge_range musi być ≥ 1.'}, status=status.HTTP_400_BAD_REQUEST)
            config.challenge_range = cr

        if 'initial_seeding' in data:
            seeding = data['initial_seeding']
            if seeding not in ('RANDOM', 'SEEDING'):
                return Response({'detail': 'initial_seeding musi być "RANDOM" lub "SEEDING".'}, status=status.HTTP_400_BAD_REQUEST)
            config.initial_seeding = seeding

        config.save()

        return Response({
            'challenge_range': config.challenge_range,
            'initial_seeding': config.initial_seeding,
        }, status=status.HTTP_200_OK)


class LadderSeedView(APIView):
    """
    Zarządzanie pozycjami (seed_number) uczestników drabinki przez organizatora.

    POST /api/tournaments/{pk}/ladder/seeds/
      Swap dwóch uczestników: zamienia ich seed_number atomowo w transakcji.
      Body: { "participant_a_id": int, "participant_b_id": int }

    PATCH /api/tournaments/{pk}/ladder/seeds/
      Bezpośrednie ustawienie seed_number dla uczestnika.
      Body: { "participant_id": int, "seed_number": int }
      Jeśli seed_number jest już zajęty przez innego uczestnika → zwraca błąd (409).
      Użyj POST (swap) zamiast PATCH jeśli chcesz zamienić dwie pozycje.

    Auth: IsAuthenticated + (created_by lub is_staff)
    Tylko turnieje LDR. Dozwolone statusy: DRF, REG, SCH.
    Turniej ACT/FIN/CNC — zablokowane (pozycje zmieniają się przez wyzwania).
    """
    permission_classes = [IsAuthenticated]

    def _get_tournament_and_check(self, request, pk):
        """Wspólna walidacja — zwraca (tournament, error_response)."""
        try:
            tournament = Tournament.objects.get(pk=pk)
        except Tournament.DoesNotExist:
            return None, Response({'detail': 'Turniej nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        if tournament.tournament_type != Tournament.TournamentType.LADDER:
            return None, Response(
                {'detail': 'Endpoint /ladder/seeds/ obsługuje tylko turnieje LDR.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_organizer = (
            request.user.is_staff or
            tournament.created_by_id == request.user.id
        )
        if not is_organizer:
            return None, Response({'detail': 'Brak uprawnień.'}, status=status.HTTP_403_FORBIDDEN)

        if tournament.status in ('FIN', 'CNC'):
            return None, Response(
                {'detail': 'Edycja pozycji niedostępna dla zakończonego lub anulowanego turnieju.'},
                status=status.HTTP_409_CONFLICT,
            )
        if tournament.status == 'ACT':
            # W ACT pozycje zmieniają się przez wyzwania — blokuj edycję,
            # chyba że są uczestnicy bez seedów (błąd migracyjny — pozwól naprawić).
            from apps.tournaments.models import Participant as _PCheck
            missing = _PCheck.objects.filter(tournament=tournament, seed_number__isnull=True).exists()
            if not missing:
                return None, Response(
                    {'detail': 'Turniej aktywny — pozycje zmieniają się przez wyzwania, nie przez ręczną edycję.'},
                    status=status.HTTP_409_CONFLICT,
                )

        return tournament, None

    def post(self, request, pk):
        """Swap seed_number dwóch uczestników (atomowy)."""
        tournament, err = self._get_tournament_and_check(request, pk)
        if err:
            return err

        id_a = request.data.get('participant_a_id')
        id_b = request.data.get('participant_b_id')

        if id_a is None or id_b is None:
            return Response(
                {'detail': 'Wymagane pola: participant_a_id, participant_b_id.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            id_a, id_b = int(id_a), int(id_b)
        except (TypeError, ValueError):
            return Response(
                {'detail': 'participant_a_id i participant_b_id muszą być liczbami.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if id_a == id_b:
            return Response(
                {'detail': 'Uczestnicy muszą być różni.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.db import transaction as _tx
        from apps.tournaments.models import Participant as _P

        try:
            with _tx.atomic():
                p_a = _P.objects.select_for_update().get(pk=id_a, tournament=tournament)
                p_b = _P.objects.select_for_update().get(pk=id_b, tournament=tournament)
                seed_a, seed_b = p_a.seed_number, p_b.seed_number
                p_a.seed_number = seed_b
                p_b.seed_number = seed_a
                p_a.save(update_fields=['seed_number'])
                p_b.save(update_fields=['seed_number'])
        except _P.DoesNotExist:
            return Response(
                {'detail': 'Jeden lub obaj uczestnicy nie należą do tego turnieju.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({
            'participant_a': {'id': p_a.id, 'display_name': p_a.display_name, 'seed_number': p_a.seed_number},
            'participant_b': {'id': p_b.id, 'display_name': p_b.display_name, 'seed_number': p_b.seed_number},
        }, status=status.HTTP_200_OK)

    def patch(self, request, pk):
        """Ustaw seed_number bezpośrednio dla jednego uczestnika."""
        tournament, err = self._get_tournament_and_check(request, pk)
        if err:
            return err

        participant_id = request.data.get('participant_id')
        new_seed       = request.data.get('seed_number')

        if participant_id is None or new_seed is None:
            return Response(
                {'detail': 'Wymagane pola: participant_id, seed_number.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            participant_id = int(participant_id)
            new_seed       = int(new_seed)
        except (TypeError, ValueError):
            return Response(
                {'detail': 'participant_id i seed_number muszą być liczbami.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new_seed < 1:
            return Response(
                {'detail': 'seed_number musi być ≥ 1.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.tournaments.models import Participant as _P
        from django.db import transaction as _tx

        with _tx.atomic():
            try:
                participant = _P.objects.select_for_update().get(pk=participant_id, tournament=tournament)
            except _P.DoesNotExist:
                return Response(
                    {'detail': 'Uczestnik nie należy do tego turnieju.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Sprawdź duplikat
            conflict = _P.objects.filter(
                tournament=tournament, seed_number=new_seed
            ).exclude(pk=participant_id).first()
            if conflict:
                return Response(
                    {'detail': f'Pozycja {new_seed} jest już zajęta przez „{conflict.display_name}". Użyj zamiany (swap).'},
                    status=status.HTTP_409_CONFLICT,
                )

            participant.seed_number = new_seed
            participant.save(update_fields=['seed_number'])

        return Response({
            'id': participant.id,
            'display_name': participant.display_name,
            'seed_number': participant.seed_number,
        }, status=status.HTTP_200_OK)


# ══════════════════════════════════════════════════════════════════════════════
# LADDER — REST API
# ══════════════════════════════════════════════════════════════════════════════

class LadderView(APIView):
    """
    GET /api/tournaments/<pk>/ladder/

    Zwraca dane drabinki liderów:
      - ranking: uczestnicy posortowani po seed_number
      - available_challenges: participant IDs które zalogowany user może wyzwać
      - active_challenges: aktywne mecze (SCH/INP) gdzie user jest uczestnikiem
      - recent_matches: ostatnie 10 zakończonych meczów LDR
      - stats: statystyki turnieju

    Auth: IsAuthenticatedOrReadOnly — ranking publiczny, challenge data tylko zalogowanemu.
    """
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, pk):
        from apps.tournaments.models import (
            Tournament, TournamentsMatch, Participant, ChallengeRejection,
        )
        from django.db.models import Q, Max, Count

        try:
            tournament = Tournament.objects.select_related('ladder_config').get(
                pk=pk,
                tournament_type=Tournament.TournamentType.LADDER,
            )
        except Tournament.DoesNotExist:
            return Response(
                {'detail': 'Turniej drabinkowy nie istnieje.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        participants = list(
            tournament.participants
            .filter(status__in=['ACT', 'REG'])
            .order_by('seed_number', 'pk')
            .select_related('user')
        )

        # Aktywne mecze (SCH/INP/WAI) — żeby wiedzieć kto jest zajęty
        active_statuses = [
            TournamentsMatch.Status.WAITING.value,
            TournamentsMatch.Status.SCHEDULED.value,
            TournamentsMatch.Status.IN_PROGRESS.value,
        ]
        active_matches_qs = TournamentsMatch.objects.filter(
            tournament=tournament, status__in=active_statuses
        ).select_related('participant1', 'participant2', 'participant1__user', 'participant2__user')

        busy_ids = set()
        for m in active_matches_qs:
            if m.participant1_id:
                busy_ids.add(m.participant1_id)
            if m.participant2_id:
                busy_ids.add(m.participant2_id)

        # Ranking
        ranking = []
        for p in participants:
            ranking.append({
                'id': p.id,
                'display_name': p.display_name,
                'seed_number': p.seed_number,
                'status': p.status,
                'user_id': p.user_id,
                'is_busy': p.id in busy_ids,
            })

        # Dane specyficzne dla zalogowanego użytkownika
        available_challenge_ids = []
        active_challenges = []
        rejected_by_ids = []
        my_participant_id = None

        if request.user.is_authenticated:
            user_participant = next(
                (p for p in participants if p.user_id == request.user.pk), None
            )
            # Debel LDR: partner pary może też wyzywać — sprawdź TeamMember
            if user_participant is None:
                from apps.tournaments.models import TeamMember as _TM
                tm = _TM.objects.filter(
                    user=request.user,
                    participant__tournament=tournament,
                ).exclude(participant__status='WDN').select_related('participant').first()
                if tm:
                    user_participant = next(
                        (p for p in participants if p.id == tm.participant_id), None
                    )
            if user_participant:
                my_participant_id = user_participant.id

            if user_participant and tournament.ladder_config:
                cfg = tournament.ladder_config
                # Gracze w zasięgu challengerange (wyżej w rankingu, nie zajęci, nie "ja")
                if user_participant.seed_number is not None:
                    min_seed = max(1, user_participant.seed_number - cfg.challenge_range)
                    available_challenge_ids = [
                        p['id'] for p in ranking
                        if (
                            p['seed_number'] is not None
                            and min_seed <= p['seed_number'] < user_participant.seed_number
                            and not p['is_busy']
                            and p['id'] != user_participant.id
                        )
                    ]

                # Aktywne wyzwania user_participanta
                user_active = active_matches_qs.filter(
                    Q(participant1=user_participant) | Q(participant2=user_participant)
                )
                for m in user_active:
                    p1 = m.participant1
                    p2 = m.participant2
                    active_challenges.append({
                        'match_id': m.id,
                        'status': m.status,
                        'challenger': {
                            'id': p1.id if p1 else None,
                            'display_name': p1.display_name if p1 else None,
                        },
                        'challenged': {
                            'id': p2.id if p2 else None,
                            'display_name': p2.display_name if p2 else None,
                        },
                        'i_am_challenger': (p1 is not None and p1.id == user_participant.id),
                        'scheduled_time': m.scheduled_time.isoformat() if m.scheduled_time else None,
                    })

                # Kto odrzucił nasze wyzwania (blokada w tej "rundzie")
                rejected_by_ids = list(
                    ChallengeRejection.objects.filter(
                        tournament=tournament,
                        challenger_participant=user_participant,
                    ).values_list('rejecting_participant_id', flat=True)
                )

        # Ostatnie 10 zakończonych meczów
        recent_matches_qs = (
            TournamentsMatch.objects
            .filter(tournament=tournament, status=TournamentsMatch.Status.COMPLETED.value)
            .select_related(
                'participant1', 'participant2', 'winner',
                'participant1__user', 'participant2__user',
            )
            .order_by('-pk')[:10]
        )
        recent_matches = []
        for m in recent_matches_qs:
            score_parts = []
            for i in range(1, 4):
                s1 = getattr(m, f'set{i}_p1_score', None)
                s2 = getattr(m, f'set{i}_p2_score', None)
                if s1 is not None and s2 is not None:
                    score_parts.append(f'{s1}:{s2}')
            recent_matches.append({
                'match_id': m.id,
                'status': m.status,
                'challenger': {
                    'id': m.participant1.id if m.participant1 else None,
                    'display_name': m.participant1.display_name if m.participant1 else None,
                },
                'challenged': {
                    'id': m.participant2.id if m.participant2 else None,
                    'display_name': m.participant2.display_name if m.participant2 else None,
                },
                'winner_id': m.winner_id,
                'winner_name': m.winner.display_name if m.winner else None,
                'score': ' '.join(score_parts) if score_parts else None,
                'scheduled_time': m.scheduled_time.isoformat() if m.scheduled_time else None,
            })

        # Statystyki
        completed_count = TournamentsMatch.objects.filter(
            tournament=tournament, status=TournamentsMatch.Status.COMPLETED.value
        ).count()

        ldr_cfg = tournament.ladder_config
        return Response({
            'tournament_id': tournament.pk,
            'tournament_status': tournament.status,
            'challenge_range': ldr_cfg.challenge_range if ldr_cfg else 3,
            'initial_seeding': ldr_cfg.initial_seeding if ldr_cfg else 'SEEDING',
            'my_participant_id': my_participant_id,
            'ranking': ranking,
            'available_challenge_ids': available_challenge_ids,
            'active_challenges': active_challenges,
            'rejected_by_ids': rejected_by_ids,
            'recent_matches': recent_matches,
            'stats': {
                'completed_matches': completed_count,
                'total_participants': len(participants),
            },
        }, status=status.HTTP_200_OK)


class LadderChallengeView(APIView):
    """
    POST /api/tournaments/<pk>/challenge/

    Rzuca wyzwanie innemu graczowi w drabince liderów.

    Body: { "challenged_id": int }  — participant ID gracza do wyzwania

    Walidacje:
      - turniej typu LDR i status ACT
      - obaj gracze aktywni w tym turnieju
      - challenged w zasięgu challenge_range powyżej challengera
      - żaden z graczy nie ma aktywnego meczu (SCH/INP/WAI)
      - brak istniejącego ChallengeRejection dla tej pary w tej rundzie

    Odpowiedź 201: { match_id, challenger_id, challenged_id, status }

    Auth: IsAuthenticated
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from apps.tournaments.models import (
            Tournament, TournamentsMatch, Participant, ChallengeRejection, LadderConfig,
        )
        from django.db.models import Q, Max

        try:
            tournament = Tournament.objects.select_related('ladder_config').get(
                pk=pk,
                tournament_type=Tournament.TournamentType.LADDER,
            )
        except Tournament.DoesNotExist:
            return Response(
                {'detail': 'Turniej drabinkowy nie istnieje.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if tournament.status != Tournament.Status.ACTIVE.value:
            return Response(
                {'detail': 'Wyzwania można rzucać tylko gdy turniej jest aktywny (ACT).'},
                status=status.HTTP_409_CONFLICT,
            )

        challenged_id = request.data.get('challenged_id')
        if not challenged_id:
            return Response(
                {'detail': 'Pole challenged_id jest wymagane.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            challenged_id = int(challenged_id)
        except (ValueError, TypeError):
            return Response(
                {'detail': 'challenged_id musi być liczbą całkowitą.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Pobierz uczestnika zalogowanego usera (kapitan lub partner pary)
        challenger = Participant.objects.filter(
            tournament=tournament,
            user=request.user,
            status__in=['ACT', 'REG'],
        ).first()
        if challenger is None:
            # Debel LDR: sprawdź czy user jest partnerem pary (TeamMember)
            from apps.tournaments.models import TeamMember as _TM
            tm = _TM.objects.filter(
                user=request.user,
                participant__tournament=tournament,
                participant__status__in=['ACT', 'REG'],
            ).select_related('participant').first()
            if tm:
                challenger = tm.participant
        if challenger is None:
            return Response(
                {'detail': 'Nie jesteś uczestnikiem tego turnieju.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Pobierz challenged participant
        try:
            challenged = Participant.objects.get(
                pk=challenged_id,
                tournament=tournament,
                status__in=['ACT', 'REG'],
            )
        except Participant.DoesNotExist:
            return Response(
                {'detail': 'Wskazany uczestnik nie istnieje lub nie jest aktywny w tym turnieju.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if challenger.id == challenged.id:
            return Response(
                {'detail': 'Nie możesz wyzwać samego siebie.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Sprawdź zasięg challenge_range
        cfg = tournament.ladder_config
        if challenger.seed_number is None or challenged.seed_number is None:
            return Response(
                {'detail': 'Nie można rzucić wyzwania — brakuje pozycji startowej (seed). Skontaktuj się z organizatorem.'},
                status=status.HTTP_409_CONFLICT,
            )
        if cfg:
            min_seed = max(1, challenger.seed_number - cfg.challenge_range)
            if not (min_seed <= challenged.seed_number < challenger.seed_number):
                return Response(
                    {
                        'detail': (
                            f'Możesz wyzwać tylko graczy na pozycjach '
                            f'{min_seed}–{challenger.seed_number - 1}. '
                            f'Pozycja wyzwanego: {challenged.seed_number}.'
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

        # Sprawdź czy któryś gracz ma aktywny mecz
        active_statuses = [
            TournamentsMatch.Status.WAITING.value,
            TournamentsMatch.Status.SCHEDULED.value,
            TournamentsMatch.Status.IN_PROGRESS.value,
        ]
        has_active = TournamentsMatch.objects.filter(
            tournament=tournament,
            status__in=active_statuses,
        ).filter(
            Q(participant1=challenger) | Q(participant2=challenger) |
            Q(participant1=challenged) | Q(participant2=challenged)
        ).exists()

        if has_active:
            return Response(
                {'detail': 'Jeden z graczy ma już aktywne wyzwanie lub mecz w toku.'},
                status=status.HTTP_409_CONFLICT,
            )

        # Sprawdź ChallengeRejection — czy challenged odrzucił nasze wyzwanie w tej rundzie
        already_rejected = ChallengeRejection.objects.filter(
            tournament=tournament,
            rejecting_participant=challenged,
            challenger_participant=challenger,
        ).exists()

        if already_rejected:
            return Response(
                {'detail': 'Ten gracz odrzucił już Twoje wyzwanie w bieżącej rundzie.'},
                status=status.HTTP_409_CONFLICT,
            )

        # Ustal match_index (auto-increment w obrębie turnieju)
        max_index = TournamentsMatch.objects.filter(tournament=tournament).aggregate(
            m=Max('match_index')
        )['m'] or 0
        next_index = max_index + 1

        # Unikamy kolizji unique_together (tournament, bracket_type, round_number, match_index)
        # przez użycie round_number=0 dla meczów challenge (nie są to rundy bracketowe)
        match = TournamentsMatch.objects.create(
            tournament=tournament,
            participant1=challenger,
            participant2=challenged,
            status=TournamentsMatch.Status.SCHEDULED.value,
            round_number=0,
            match_index=next_index,
        )

        logger.info(
            '[ladder] Wyzwanie rzucone: %s → %s w turnieju id=%d, mecz id=%d',
            challenger.display_name, challenged.display_name, tournament.pk, match.pk,
        )

        # Notyfikacja: powiadom wyzwanego
        if challenged.user_id and challenged.user:
            from notifications.helpers import notify
            notify(
                challenged.user,
                f'🎾 {challenger.display_name} rzucił Ci wyzwanie w turnieju „{tournament.name}". '
                f'Zaakceptuj lub odrzuć wyzwanie.',
                target_url=f'/tournaments/{tournament.pk}',
                event_type='tournament.ladder.challenge_sent',
            )

        return Response({
            'match_id': match.pk,
            'challenger_id': challenger.id,
            'challenger_name': challenger.display_name,
            'challenged_id': challenged.id,
            'challenged_name': challenged.display_name,
            'status': match.status,
        }, status=status.HTTP_201_CREATED)


class LadderChallengeActionView(APIView):
    """
    POST /api/tournaments/<pk>/challenges/<match_id>/accept/
    POST /api/tournaments/<pk>/challenges/<match_id>/reject/

    Accept: zmienia status meczu SCH → INP (w trakcie).
    Reject: zmienia status meczu SCH → CNC, tworzy ChallengeRejection record.

    Tylko challenged player (participant2) może accept/reject.
    Auth: IsAuthenticated
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, match_id, action):
        from apps.tournaments.models import (
            Tournament, TournamentsMatch, ChallengeRejection,
        )

        if action not in ('accept', 'reject'):
            return Response(
                {'detail': 'Nieznana akcja. Użyj: accept lub reject.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            tournament = Tournament.objects.get(
                pk=pk,
                tournament_type=Tournament.TournamentType.LADDER,
            )
        except Tournament.DoesNotExist:
            return Response(
                {'detail': 'Turniej drabinkowy nie istnieje.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            match = TournamentsMatch.objects.select_related(
                'participant1', 'participant2',
                'participant1__user', 'participant2__user',
            ).get(pk=match_id, tournament=tournament)
        except TournamentsMatch.DoesNotExist:
            return Response(
                {'detail': 'Mecz nie istnieje.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if match.status != TournamentsMatch.Status.SCHEDULED.value:
            return Response(
                {'detail': f'Akcja możliwa tylko dla meczu ze statusem SCH. Obecny: {match.status}.'},
                status=status.HTTP_409_CONFLICT,
            )

        # Tylko challenged (participant2) może accept/reject
        challenged = match.participant2
        if challenged is None or challenged.user_id != request.user.pk:
            # Organizator / staff może też zaakceptować/odrzucić
            is_organizer = request.user == tournament.created_by or request.user.is_staff
            if not is_organizer:
                return Response(
                    {'detail': 'Tylko wyzwany gracz lub organizator turnieju może wykonać tę akcję.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        from notifications.helpers import notify

        if action == 'accept':
            match.status = TournamentsMatch.Status.IN_PROGRESS.value
            match.save(update_fields=['status'])
            logger.info(
                '[ladder] Wyzwanie zaakceptowane: mecz id=%d w turnieju id=%d',
                match.pk, tournament.pk,
            )
            # Powiadom challengera (participant1) o akceptacji
            challenger = match.participant1
            if challenger and challenger.user:
                notify(
                    challenger.user,
                    f'✅ {challenged.display_name if challenged else "Przeciwnik"} zaakceptował Twoje wyzwanie '
                    f'w turnieju „{tournament.name}". Czas grać!',
                    target_url=f'/tournaments/{tournament.pk}',
                    event_type='tournament.ladder.challenge_accepted',
                )
            return Response({
                'match_id': match.pk,
                'status': match.status,
                'detail': 'Wyzwanie zaakceptowane. Mecz w toku.',
            }, status=status.HTTP_200_OK)

        # action == 'reject'
        match.status = TournamentsMatch.Status.CANCELLED.value
        match.save(update_fields=['status'])

        # Zapisz odrzucenie — blokuje powtórne wyzwanie w tej rundzie
        challenger = match.participant1
        if challenger is not None:
            ChallengeRejection.objects.get_or_create(
                tournament=tournament,
                rejecting_participant=challenged,
                challenger_participant=challenger,
            )

        logger.info(
            '[ladder] Wyzwanie odrzucone: mecz id=%d w turnieju id=%d',
            match.pk, tournament.pk,
        )
        # Powiadom challengera (participant1) o odrzuceniu
        if challenger and challenger.user:
            notify(
                challenger.user,
                f'❌ {challenged.display_name if challenged else "Przeciwnik"} odrzucił Twoje wyzwanie '
                f'w turnieju „{tournament.name}".',
                target_url=f'/tournaments/{tournament.pk}',
                event_type='tournament.ladder.challenge_rejected',
            )
        return Response({
            'match_id': match.pk,
            'status': match.status,
            'detail': 'Wyzwanie odrzucone.',
        }, status=status.HTTP_200_OK)
