from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.matches.models import Match
from apps.matches import tools as match_tools
from apps.matches.api.serializers import MatchCreateSerializer, MatchHistorySerializer
from apps.users.api.serializers import UserDetailsSerializer

class MatchCreateView(generics.CreateAPIView):
    """API endpoint to create a new friendly match."""
    serializer_class = MatchCreateSerializer
    permission_classes = [IsAuthenticated]


class MatchDetailView(generics.RetrieveAPIView):
    """
    GET  /api/matches/<id>/ — szczegóły meczu towarzyskiego + pole can_edit.
    PATCH /api/matches/<id>/ — edycja wyniku przez uczestnika lub is_staff.

    PATCH body (wszystkie opcjonalne, ale p1_set1 i p2_set1 wymagane jeśli wpisujemy wynik):
      p1_set1, p2_set1  — wyniki 1. seta (wymagane)
      p1_set2, p2_set2  — wyniki 2. seta (opcjonalne)
      p1_set3, p2_set3  — wyniki 3. seta (opcjonalne)
      match_date        — data meczu ISO 8601 (opcjonalne)

    Uprawnienia PATCH: uczestnik meczu (p1/p2/p3/p4) lub is_staff.
    """
    serializer_class = MatchHistorySerializer
    permission_classes = [IsAuthenticated]
    queryset = Match.objects.select_related('p1', 'p2', 'p3', 'p4').all()

    def _players(self, instance):
        ids = [instance.p1_id, instance.p2_id]
        if instance.p3_id:
            ids.append(instance.p3_id)
        if instance.p4_id:
            ids.append(instance.p4_id)
        return ids

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        is_participant = request.user.pk in self._players(instance)
        data['can_edit'] = request.user.is_staff or is_participant

        # Numery telefonów uczestników — widoczne tylko dla uczestników lub staff.
        # Nigdy w listach/search — tylko w kontekście konkretnego meczu.
        if is_participant or request.user.is_staff:
            def phone_for(player_data):
                if not player_data or not player_data.get('id'):
                    return None
                try:
                    from apps.users.models import Profile
                    p = Profile.objects.get(user_id=player_data['id'])
                    return p.phone_number or None
                except Profile.DoesNotExist:
                    return None

            for key in ('p1', 'p2', 'p3', 'p4'):
                if data.get(key):
                    data[key]['phone_number'] = phone_for(data[key])

        return Response(data)

    def patch(self, request, *args, **kwargs):
        instance = self.get_object()

        if not (request.user.is_staff or request.user.pk in self._players(instance)):
            return Response(
                {'detail': 'Brak uprawnień. Tylko uczestnik meczu lub administrator może edytować wynik.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        def _int_or_none(key):
            v = request.data.get(key)
            if v is None or v == '':
                return None, False
            try:
                return int(v), False
            except (ValueError, TypeError):
                return None, True  # błąd

        errors = {}
        sets = {}
        for field in ('p1_set1', 'p2_set1', 'p1_set2', 'p2_set2', 'p1_set3', 'p2_set3'):
            val, err = _int_or_none(field)
            if err:
                errors[field] = 'Musi być liczbą całkowitą lub null.'
            else:
                sets[field] = val

        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        # set1 wymagane jeśli w ogóle wpisujemy wynik
        if 'p1_set1' in request.data or 'p2_set1' in request.data:
            if sets.get('p1_set1') is None or sets.get('p2_set1') is None:
                return Response(
                    {'detail': 'p1_set1 i p2_set1 są wymagane.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Wartości ujemne niedozwolone
        for field, val in sets.items():
            if val is not None and val < 0:
                return Response(
                    {'detail': f'Pole „{field}" nie może być ujemne.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Walidacja tenisowa setów (defence-in-depth — frontend ma własną)
        from apps.matches.tools import validate_tennis_set
        for s in (1, 2, 3):
            a = sets.get(f'p1_set{s}')
            b = sets.get(f'p2_set{s}')
            if a is not None and b is not None:
                err = validate_tennis_set(a, b, s)
                if err:
                    return Response({'detail': err}, status=status.HTTP_400_BAD_REQUEST)
            elif (a is None) != (b is None):
                return Response(
                    {'detail': f'Set {s}: wpisz wynik dla obu stron lub żaden.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        update_fields = []
        for field, val in sets.items():
            if field in request.data:
                setattr(instance, field, val)
                update_fields.append(field)

        if 'match_date' in request.data:
            from django.utils.dateparse import parse_date
            raw = request.data.get('match_date')
            parsed = parse_date(str(raw)) if raw else None
            if raw and parsed is None:
                return Response(
                    {'detail': 'Nieprawidłowy format match_date (oczekiwany YYYY-MM-DD).'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            instance.match_date = parsed
            update_fields.append('match_date')

        # Friendly matches: wynik zawsze CONFIRMED od razu — nie wymagamy confirm drugiej osoby.
        # reported_by = kto zgłosił; confirmed_by = None (nie było obowiązkowego flow).
        if update_fields:
            instance.score_status = 'CONFIRMED'
            instance.reported_by = request.user
            instance.confirmed_by = None
            update_fields += ['score_status', 'reported_by', 'confirmed_by']
            instance.save(update_fields=update_fields)

        serializer = self.get_serializer(instance)
        data = serializer.data
        data['can_edit'] = True
        return Response(data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()

        if not (request.user.is_staff or request.user.pk in self._players(instance)):
            return Response(
                {'detail': 'Brak uprawnień. Tylko uczestnik meczu lub administrator może usunąć mecz.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MatchHistoryView(generics.ListAPIView):
    """API endpoint that lists match history with calculated results.

    Returns both friendly Match objects and completed TournamentMatches
    (converted to a common dict format by Results.get_matches).
    Tournament entries have is_tournament=True and tournament_id set.
    """
    serializer_class = MatchHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        filters = match_tools.prepare_filters(self.request)
        results_obj = match_tools.Results(self.request, sort="match_date", **filters)
        return results_obj.qs

    def list(self, request, *args, **kwargs):
        filters = match_tools.prepare_filters(request)
        results_obj = match_tools.Results(request, sort="match_date", **filters)

        def build_player(m, key):
            uid = m.get(f'{key}_id')
            if not uid:
                return None
            full = m.get(key) or ''
            parts = full.strip().split(' ', 1) if full else []
            return {
                'id': uid,
                'username': m.get(f'{key}_username') or '',
                'first_name': parts[0] if parts else '',
                'last_name': parts[1] if len(parts) > 1 else '',
            }

        data = []
        for m in results_obj.matches:
            data.append({
                'id': m.get('id'),
                'p1': build_player(m, 'p1'),
                'p2': build_player(m, 'p2'),
                'p3': build_player(m, 'p3'),
                'p4': build_player(m, 'p4'),
                'p1_set1': m.get('p1_set1'),
                'p1_set2': m.get('p1_set2'),
                'p1_set3': m.get('p1_set3'),
                'p2_set1': m.get('p2_set1'),
                'p2_set2': m.get('p2_set2'),
                'p2_set3': m.get('p2_set3'),
                'match_double': m.get('match_double', False),
                'description': m.get('description'),
                'match_date': str(m.get('match_date', '')),
                'score_status': m.get('score_status'),
                'reported_by': None,
                'confirmed_by': None,
                'win': m.get('win'),
                'user': m.get('user'),
                'p1_win_set': m.get('p1_win_set', 0),
                'p2_win_set': m.get('p2_win_set', 0),
                'p1_win_gem': m.get('p1_win_gem', 0),
                'p2_win_gem': m.get('p2_win_gem', 0),
                'is_tournament': m.get('is_tournament', False),
                'tournament_id': m.get('tournament_id'),
                'tournament_name': m.get('tournament_name'),
                'tournament_type': m.get('tournament_type'),
            })

        return Response(data)


class ClubMatchesView(APIView):
    """
    GET /api/matches/club/ — mecze rozgrywane w klubie.

    Parametry query:
      ?source=tournament|friendly|all  — źródło meczów (domyślnie tournament)
      ?limit=30                        — liczba wyników (domyślnie 30, max 100)
      ?match_double=0|1                — filtr singiel/debel
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.tournaments.models import TournamentsMatch, Tournament
        from apps.tournaments.tools import _partner_user
        from django.db.models import Q
        from datetime import date as date_type

        try:
            limit = min(int(request.GET.get('limit', 30)), 100)
        except (ValueError, TypeError):
            limit = 30

        source = request.GET.get('source', 'tournament')
        match_double = request.GET.get('match_double')

        def user_full_name(u):
            if not u:
                return None
            full = ' '.join(filter(None, [u.first_name, u.last_name]))
            return full or u.username

        data = []

        if source in ('tournament', 'all'):
            def player_name(participant):
                if not participant or not participant.user:
                    return None
                return user_full_name(participant.user)

            qs = TournamentsMatch.objects.filter(
                status=TournamentsMatch.Status.COMPLETED.value,
                tournament__status__in=['ACT', 'FIN'],
            ).select_related(
                'tournament',
                'participant1__user', 'participant2__user',
                'participant3__user', 'participant4__user',
                'winner__user',
            ).prefetch_related(
                'participant1__members__user',
                'participant2__members__user',
            ).exclude(
                tournament__tournament_type__in=[
                    Tournament.TournamentType.SINGLE_ELIMINATION.value,
                    Tournament.TournamentType.DOUBLE_ELIMINATION.value,
                ],
                round_number=1,
                participant2__isnull=True,
            ).order_by('-scheduled_time')

            if match_double == '0':
                qs = qs.filter(
                    Q(participant3__isnull=True) | Q(participant4__isnull=True)
                ).exclude(tournament__match_format=Tournament.MatchFormat.DOUBLES.value)
            elif match_double == '1':
                qs = qs.filter(
                    Q(participant3__isnull=False, participant4__isnull=False) |
                    Q(tournament__match_format=Tournament.MatchFormat.DOUBLES.value)
                )

            if source == 'tournament':
                qs = qs[:limit]

            for m in qs:
                is_double = bool(
                    m.participant3_id or m.participant4_id or
                    m.tournament.match_format == Tournament.MatchFormat.DOUBLES.value
                )
                match_date = (
                    m.scheduled_time.date() if m.scheduled_time
                    else m.tournament.start_date.date() if m.tournament.start_date
                    else None
                )
                if m.winner_id and m.winner_id in (m.participant1_id, m.participant3_id):
                    winner_side = 'p1'
                elif m.winner_id and m.winner_id in (m.participant2_id, m.participant4_id):
                    winner_side = 'p2'
                else:
                    winner_side = None

                if is_double and not m.participant3_id and not m.participant4_id:
                    p1_id = m.participant1.user_id if m.participant1 and m.participant1.user else None
                    p2_id = m.participant2.user_id if m.participant2 and m.participant2.user else None
                    p3 = user_full_name(_partner_user(m.participant1, p1_id))
                    p4 = user_full_name(_partner_user(m.participant2, p2_id))
                else:
                    p3 = player_name(m.participant3) if is_double else None
                    p4 = player_name(m.participant4) if is_double else None

                data.append({
                    'id': m.pk,
                    'source': 'tournament',
                    'tournament_id': m.tournament_id,
                    'tournament_name': m.tournament.name,
                    'tournament_type': m.tournament.tournament_type,
                    'p1': player_name(m.participant1),
                    'p2': player_name(m.participant2),
                    'p3': p3,
                    'p4': p4,
                    'set1': f"{m.set1_p1_score}:{m.set1_p2_score}" if m.set1_p1_score is not None else None,
                    'set2': f"{m.set2_p1_score}:{m.set2_p2_score}" if m.set2_p1_score is not None else None,
                    'set3': f"{m.set3_p1_score}:{m.set3_p2_score}" if m.set3_p1_score is not None else None,
                    'winner': player_name(m.winner) if m.winner_id else None,
                    'winner_side': winner_side,
                    'match_double': is_double,
                    'match_date': str(match_date) if match_date else None,
                })

        if source in ('friendly', 'all'):
            fqs = Match.objects.filter(
                score_status=Match.ScoreStatus.CONFIRMED,
            ).select_related('p1', 'p2', 'p3', 'p4').order_by('-match_date')

            if match_double == '0':
                fqs = fqs.filter(match_double=False)
            elif match_double == '1':
                fqs = fqs.filter(match_double=True)

            if source == 'friendly':
                fqs = fqs[:limit]

            for m in fqs:
                def _fmt_set(a, b):
                    if a is None or b is None:
                        return None
                    return f"{a}:{b}"

                # winner_side: strona z więcej wygranych setów
                sets = [
                    (m.p1_set1, m.p2_set1),
                ]
                if m.p1_set2 is not None and m.p2_set2 is not None:
                    sets.append((m.p1_set2, m.p2_set2))
                if m.p1_set3 is not None and m.p2_set3 is not None:
                    sets.append((m.p1_set3, m.p2_set3))

                p1_sets = sum(1 for a, b in sets if a > b)
                p2_sets = sum(1 for a, b in sets if b > a)
                if p1_sets > p2_sets:
                    winner_side = 'p1'
                    winner = user_full_name(m.p1)
                elif p2_sets > p1_sets:
                    winner_side = 'p2'
                    winner = user_full_name(m.p2)
                else:
                    winner_side = None
                    winner = None

                data.append({
                    'id': m.pk,
                    'source': 'friendly',
                    'tournament_id': None,
                    'tournament_name': None,
                    'tournament_type': 'FRL',
                    'p1': user_full_name(m.p1),
                    'p2': user_full_name(m.p2),
                    'p3': user_full_name(m.p3) if m.match_double else None,
                    'p4': user_full_name(m.p4) if m.match_double else None,
                    'set1': _fmt_set(m.p1_set1, m.p2_set1),
                    'set2': _fmt_set(m.p1_set2, m.p2_set2),
                    'set3': _fmt_set(m.p1_set3, m.p2_set3),
                    'winner': winner,
                    'winner_side': winner_side,
                    'match_double': m.match_double,
                    'match_date': str(m.match_date) if m.match_date else None,
                })

        if source == 'all':
            data.sort(key=lambda x: x['match_date'] or '0000-00-00', reverse=True)
            data = data[:limit]

        return Response(data)


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
