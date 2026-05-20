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
        data['can_edit'] = request.user.is_staff or request.user.pk in self._players(instance)
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

        # score_status: staff → CONFIRMED od razu; uczestnik → PENDING (czeka na potwierdzenie)
        if update_fields:
            if request.user.is_staff:
                instance.score_status = 'CONFIRMED'
                instance.reported_by = request.user
                instance.confirmed_by = request.user
            else:
                instance.score_status = 'PENDING'
                instance.reported_by = request.user
                instance.confirmed_by = None
            update_fields += ['score_status', 'reported_by', 'confirmed_by']
            instance.save(update_fields=update_fields)

        serializer = self.get_serializer(instance)
        data = serializer.data
        data['can_edit'] = True
        return Response(data, status=status.HTTP_200_OK)


class MatchConfirmView(APIView):
    """
    POST /api/matches/<id>/confirm/

    Drugi uczestnik meczu potwierdza wynik.
    Reguły:
    - tylko uczestnik meczu (p1/p2/p3/p4) może potwierdzić
    - nie można potwierdzić własnego zgłoszenia (reported_by != request.user)
    - mecz musi być w statusie PENDING
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        try:
            instance = Match.objects.select_related('p1', 'p2', 'p3', 'p4').get(pk=pk)
        except Match.DoesNotExist:
            return Response({'detail': 'Mecz nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        player_ids = [instance.p1_id, instance.p2_id]
        if instance.p3_id:
            player_ids.append(instance.p3_id)
        if instance.p4_id:
            player_ids.append(instance.p4_id)

        if request.user.pk not in player_ids:
            return Response(
                {'detail': 'Brak uprawnień. Tylko uczestnik meczu może potwierdzić wynik.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if instance.score_status != 'PENDING':
            return Response(
                {'detail': 'Wynik nie czeka na potwierdzenie.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if instance.reported_by_id == request.user.pk:
            return Response(
                {'detail': 'Nie możesz potwierdzić własnego zgłoszenia.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance.score_status = 'CONFIRMED'
        instance.confirmed_by = request.user
        instance.save(update_fields=['score_status', 'confirmed_by'])

        serializer = MatchHistorySerializer(instance, context={'request': request})
        data = serializer.data
        data['can_edit'] = True
        return Response(data, status=status.HTTP_200_OK)


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
            })

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
