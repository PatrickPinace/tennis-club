from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'tournaments', views.TournamentViewSet, basename='tournament')

urlpatterns = [
    # Custom paths muszą być przed router.urls — DefaultRouter rejestruje
    # tournaments/<pk>/ i przechwytuje np. tournaments/create/ jako pk="create".
    path('tournaments/list/', views.TournamentListView.as_view(), name='tournament-list-api'),
    path('tournaments/mine/', views.MyTournamentsView.as_view(), name='tournament-mine-api'),
    path('tournaments/create/', views.TournamentCreateView.as_view(), name='tournament-create'),
    path('tournaments/<int:pk>/detail/', views.TournamentDetailView.as_view(), name='tournament-detail'),
    path('tournaments/<int:pk>/status/', views.TournamentStatusView.as_view(), name='tournament-status'),
    path('tournaments/<int:pk>/finish/', views.TournamentFinishView.as_view(), name='tournament-finish'),
    path('tournaments/<int:pk>/join/', views.TournamentJoinView.as_view(), name='tournament-join'),
    path('tournaments/<int:pk>/participants/', views.TournamentParticipantView.as_view(), name='tournament-participants'),
    path('tournaments/<int:pk>/participants/<int:p_pk>/', views.TournamentParticipantView.as_view(), name='tournament-participants-delete'),
    path('tournaments/<int:pk>/bracket/', views.TournamentBracketView.as_view(), name='tournament-bracket'),
    path('tournaments/<int:pk>/standings/', views.RoundRobinStandingsView.as_view(), name='tournament-standings-rr'),
    path('tournaments/<int:pk>/matches/<int:match_pk>/score/', views.RoundRobinMatchScoreView.as_view(), name='tournament-match-score'),
    
    # Configs
    path('tournaments/<int:pk>/config/', views.RoundRobinConfigUpdateView.as_view(), name='tournament-config-rr'),
    path('tournaments/<int:pk>/config/sgl/', views.EliminationConfigUpdateView.as_view(), name='tournament-config-sgl'),
    path('tournaments/<int:pk>/config/amr/', views.AmericanoConfigUpdateView.as_view(), name='tournament-config-amr'),
    path('tournaments/<int:pk>/amr/next-round/', views.AmrNextRoundView.as_view(), name='tournament-amr-next-round'),
    path('tournaments/<int:pk>/generate-matches/', views.GenerateMatchesView.as_view(), name='tournament-generate-matches'),
    # Ladder (LDR)
    path('tournaments/<int:pk>/config/ldr/', views.LadderConfigUpdateView.as_view(), name='tournament-config-ldr'),
    path('tournaments/<int:pk>/ladder/', views.LadderView.as_view(), name='tournament-ladder'),
    path('tournaments/<int:pk>/challenge/', views.LadderChallengeView.as_view(), name='tournament-ladder-challenge'),
    path('tournaments/<int:pk>/challenges/<int:match_id>/<str:action>/', views.LadderChallengeActionView.as_view(), name='tournament-ladder-challenge-action'),
    # Router na końcu — obsługuje standardowe CRUD akcje ViewSetu
    path('', include(router.urls)),
]
