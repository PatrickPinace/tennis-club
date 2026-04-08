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