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
    path('tournaments/<int:pk>/detail/', views.TournamentDetailView.as_view(), name='tournament-detail'),
    path('tournaments/<int:pk>/standings/', views.RoundRobinStandingsView.as_view(), name='tournament-rr-standings'),
    path('tournaments/<int:pk>/config/', views.RoundRobinConfigUpdateView.as_view(), name='tournament-rr-config'),
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
    path('matches/add/', views.MatchCreateView.as_view(), name='api-match-add'),
    path('users/', views.UserListView.as_view(), name='user-list'),
    path('matches/history/', views.MatchHistoryView.as_view(), name='api-match-history'),
    path('matches/filters/', views.MatchFiltersView.as_view(), name='api-match-filters'),
]