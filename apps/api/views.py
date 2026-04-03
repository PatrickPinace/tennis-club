from rest_framework import viewsets, generics, status
from rest_framework.permissions import IsAuthenticatedOrReadOnly, AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.tournaments.models import Tournament
from apps.matches import tools as match_tools
from .serializers import (TournamentSerializer, RegisterSerializer, UserDetailsSerializer, 
                          NotificationSerializer, MatchCreateSerializer, MatchHistorySerializer)
from django.contrib.auth.models import User
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
