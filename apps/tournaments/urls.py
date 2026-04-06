from django.urls import path
from . import views

app_name = 'tournaments'

urlpatterns = [
    path('', views.manage, name='manage'),
    path('<int:pk>/details/round-robin/', views.tournament_details_round_robin, name='details_round_robin'),
    path('<int:pk>/details/elimination/', views.tournament_details_single_elimination, name='details_elimination'),
    path('<int:pk>/details/double-elimination/', views.tournament_details_double_elimination, name='details_double_elimination'),
    path('<int:pk>/details/ladder/', views.tournament_details_ladder, name='details_ladder'),
    path('<int:pk>/details/swiss/', views.tournament_details_swiss, name='details_swiss'),
    path('<int:pk>/details/americano/', views.tournament_details_americano, name='details_americano'),
    path('create/', views.create_tournament, name='create_tournament'),
    path('<int:pk>/edit/', views.edit_tournament, name='edit_tournament'),
    path('<int:pk>/config/roundrobin/', views.edit_roundrobin_config, name='edit_roundrobin_config'),
    path('<int:pk>/config/elimination/', views.edit_elimination_config, name='edit_elimination_config'),
    path('<int:pk>/config/double-elimination/', views.edit_elimination_config, name='edit_double_elimination_config'),
    path('<int:pk>/config/ladder/', views.edit_ladder_config, name='edit_ladder_config'),
    path('<int:pk>/config/swiss/', views.edit_swiss_config, name='edit_swiss_config'),
    path('<int:pk>/config/americano/', views.edit_americano_config, name='edit_americano_config'),
    path('<int:pk>/participants/', views.list_participants, name='list_participants'),
    path('<int:pk>/participants/register/', views.register_participant, name='register_participant'),
    path('<int:pk>/participants/<int:participant_pk>/edit/', views.edit_participant, name='edit_participant'),
    path('<int:pk>/participants/<int:participant_pk>/members/add/', views.add_team_member, name='add_team_member'),
    path('<int:pk>/participants/<int:participant_pk>/members/<int:member_pk>/remove/', views.remove_team_member, name='remove_team_member'),
    path('<int:pk>/join/', views.request_join, name='request_join'),
    path('<int:pk>/participants/<int:participant_pk>/approve/', views.approve_participant, name='approve_participant'),
    path('<int:pk>/participants/<int:participant_pk>/reject/', views.reject_participant, name='reject_participant'),
    path('<int:pk>/participants/<int:participant_pk>/remove/', views.remove_participant, name='remove_participant'),
    path('<int:pk>/status/draft/', views.revert_to_draft, name='revert_to_draft'),
    path('<int:pk>/open-registration/', views.open_registration, name='open_registration'),
    path('<int:pk>/close-registration/', views.close_registration, name='close_registration'),
    path('<int:pk>/start/', views.start_tournament, name='start_tournament'),
    path('<int:pk>/finish/', views.finish_tournament, name='finish_tournament'),
    path('<int:pk>/delete/', views.delete_tournament, name='delete_tournament'),

    # Spotkania turniejowe
    path('<int:pk>/matches/', views.manage_matches, name='manage_matches'),
    path('<int:pk>/matches/generate/', views.generate_matches, name='generate_matches'),
    path('<int:pk>/matches/create/', views.create_match, name='create_match'),
    path('<int:pk>/matches/<int:match_pk>/edit/', views.edit_match, name='edit_match'),
    path('<int:pk>/matches/<int:match_pk>/live/', views.live_match_view, name='live_match'),
    path('<int:pk>/matches/<int:match_pk>/start/', views.start_match, name='start_match'),
    path('<int:pk>/matches/<int:match_pk>/delete/', views.delete_match, name='delete_match'),
    path('<int:pk>/matches/reset-leaderboard-locks/', views.reset_leaderboard_locks, name='reset_leaderboard_locks'),


    # Challenger
    path('<int:pk>/challenger/', views.create_challenge_match, name='create_challenge'),
    path('<int:pk>/challenger/<int:match_pk>/cancel/', views.cancel_challenge, name='cancel_challenge'),

    # Reakcje na mecze
    path('match/<int:match_pk>/react/', views.add_reaction, name='add_reaction'),
]
