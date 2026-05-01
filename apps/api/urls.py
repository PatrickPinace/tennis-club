from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from . import views

router = DefaultRouter()
router.register(r'tournaments', views.TournamentViewSet, basename='tournament')

urlpatterns = [
    # Specyficzne ścieżki PRZED router.urls — router może przechwytywać ścieżki jako pk ViewSetu
    path('tournaments/list/', views.TournamentListView.as_view(), name='tournaments-list'),
    path('tournaments/mine/', views.MyTournamentsView.as_view(), name='tournaments-mine'),
    path('tournaments/<int:pk>/detail/', views.TournamentDetailView.as_view(), name='tournament-detail'),
    path('tournaments/<int:pk>/standings/', views.RoundRobinStandingsView.as_view(), name='tournament-rr-standings'),
    path('tournaments/<int:pk>/bracket/', views.TournamentBracketView.as_view(), name='tournament-bracket'),
    path('tournaments/<int:pk>/config/sgl/', views.EliminationConfigUpdateView.as_view(), name='tournament-sgl-config'),
    path('tournaments/<int:pk>/config/amr/', views.AmericanoConfigUpdateView.as_view(), name='tournament-amr-config'),
    path('tournaments/<int:pk>/config/', views.RoundRobinConfigUpdateView.as_view(), name='tournament-rr-config'),
    path('tournaments/<int:pk>/amr/next-round/', views.AmrNextRoundView.as_view(), name='tournament-amr-next-round'),
    path('tournaments/<int:pk>/finish/', views.TournamentFinishView.as_view(), name='tournament-finish'),
    path('tournaments/<int:pk>/status/', views.TournamentStatusView.as_view(), name='tournament-status'),
    path('tournaments/<int:pk>/generate-matches/', views.GenerateMatchesView.as_view(), name='tournament-generate-matches'),
    path('tournaments/<int:pk>/participants/', views.TournamentParticipantView.as_view(), name='tournament-participants'),
    path('tournaments/<int:pk>/participants/<int:p_pk>/', views.TournamentParticipantView.as_view(), name='tournament-participant-detail'),
    path('tournaments/<int:pk>/join/', views.TournamentJoinView.as_view(), name='tournament-join'),
    path('tournaments/create/', views.TournamentCreateView.as_view(), name='tournament-create'),
    path('tournaments/<int:pk>/matches/<int:match_pk>/score/', views.RoundRobinMatchScoreView.as_view(), name='tournament-rr-match-score'),
    path('rankings/list/', views.RankingListView.as_view(), name='rankings-list'),
    path('dashboard/summary/', views.DashboardSummaryView.as_view(), name='dashboard-summary'),
    path('', include(router.urls)),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', views.RegisterView.as_view(), name='api_register'),
    path('me/', views.UserDetailsView.as_view(), name='user-details'),
    path('chats/unread-count/', views.UnreadChatMessagesCountView.as_view(), name='unread-chat-count'),
    path('notifications/', views.NotificationListView.as_view(), name='notification-list'),
    path('notifications/read-all/', views.NotificationMarkAllReadView.as_view(), name='notification-read-all'),
    path('notifications/<int:pk>/read/', views.NotificationMarkReadView.as_view(), name='notification-read'),
    path('matches/add/', views.MatchCreateView.as_view(), name='api-match-add'),
    path('users/', views.UserListView.as_view(), name='user-list'),
    path('matches/history/', views.MatchHistoryView.as_view(), name='api-match-history'),
    path('matches/filters/', views.MatchFiltersView.as_view(), name='api-match-filters'),
    path('matches/<int:pk>/', views.MatchDetailView.as_view(), name='api-match-detail'),
    path('matches/<int:pk>/confirm/', views.MatchConfirmView.as_view(), name='api-match-confirm'),
    path('admin/rebuild-rankings/', views.RebuildRankingsView.as_view(), name='admin-rebuild-rankings'),
]