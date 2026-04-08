from rest_framework import viewsets, generics, status
from rest_framework.permissions import IsAuthenticatedOrReadOnly, AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.tournaments.models import Tournament
from apps.matches import tools as match_tools
from .serializers import (TournamentSerializer, RegisterSerializer, UserDetailsSerializer, 
                          NotificationSerializer, MatchCreateSerializer, MatchHistorySerializer)
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
