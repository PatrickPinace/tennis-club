import logging
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.rankings.models import PlayerRanking
from apps.rankings.api.serializers import PlayerRankingSerializer

logger = logging.getLogger(__name__)

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
        match_type = self.request.query_params.get('type', 'SNG').upper()
        year_param = self.request.query_params.get('year', None)

        # Normalizuj typ
        if match_type not in ('SNG', 'DBL'):
            match_type = 'SNG'

        # Wyznacz sezon
        if year_param is None or year_param == '' or year_param.lower() == 'all':
            season = None  # Domyślnie: all-time
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


class RankingSeasonsView(APIView):
    """
    GET /api/rankings/seasons/ — lista dostępnych sezonów (lat) w rankingu.
    Zwraca: { "seasons": [2026, 2025, 2024, ...] }
    """
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        match_type = request.query_params.get('type', 'SNG').upper()
        if match_type not in ('SNG', 'DBL'):
            match_type = 'SNG'
        seasons = (
            PlayerRanking.objects
            .filter(match_type=match_type)
            .exclude(season=None)
            .values_list('season', flat=True)
            .distinct()
            .order_by('-season')
        )
        return Response({'seasons': list(seasons)})


class RankingCalculationInfoView(APIView):
    """
    GET /api/rankings/info/ — zwraca informacje o ostatniej i kolejnej aktualizacji rankingu.
    """
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        from apps.rankings.models import RankingCalculationInfo
        latest = RankingCalculationInfo.objects.order_by('-last_run').first()
        if latest:
            return Response({
                'last_run': latest.last_run,
                'next_run': latest.next_run,
            })
        return Response(None)


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
                {'detail': 'Wystąpił wewnętrzny błąd podczas przeliczania rankingów. Skontaktuj się z administratorem.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.info('[rankings] Ręczny rebuild zakończony: %d wpisów.', count)
        return Response({
            'rebuilt': count,
            'match_type': match_type or 'all',
            'season': season or 'all',
        }, status=status.HTTP_200_OK)
