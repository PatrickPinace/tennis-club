"""
Tennis Club v2 - URL Configuration (Minimal for MVP)
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from v2_core.views import health_check, signup, home
from v2_core import api_views, api_reservations, api_matches, api_tournaments_new as api_tournaments, api_users

urlpatterns = [
    # Health check
    path('health/', health_check, name='health_check'),

    # Admin
    path('admin/', admin.site.urls),

    # Authentication
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('signup/', signup, name='signup'),

    # Home
    path('', home, name='home'),

    # API for Astro frontend
    path('api/auth/', include('apps.users.api_urls')),
    path('api/dashboard/stats/', api_views.dashboard_stats, name='dashboard_stats'),

    # Reservations API (Sprint 3)
    path('api/facilities/', api_reservations.facilities_list, name='facilities_list'),
    path('api/courts/', api_reservations.courts_list, name='courts_list'),
    path('api/reservations/availability/', api_reservations.reservations_availability, name='reservations_availability'),
    path('api/reservations/my/', api_reservations.my_reservations, name='my_reservations'),
    path('api/reservations/', api_reservations.create_reservation, name='create_reservation'),
    path('api/reservations/<int:reservation_id>/', api_reservations.cancel_reservation, name='cancel_reservation'),

    # Matches API (Sprint 4)
    path('api/matches/', api_matches.matches_list, name='matches_list'),
    path('api/matches/<int:match_id>/', api_matches.match_detail, name='match_detail'),
    path('api/matches/create/', api_matches.create_match, name='create_match'),
    path('api/matches/<int:match_id>/update/', api_matches.update_match_result, name='update_match_result'),
    path('api/matches/<int:match_id>/cancel/', api_matches.cancel_match, name='cancel_match'),

    # Tournaments API (Sprint 4 - Full Implementation)
    path('api/tournaments/', api_tournaments.tournaments_list_create, name='tournaments_list_create'),
    path('api/tournaments/<int:tournament_id>/', api_tournaments.tournament_detail, name='tournament_detail'),

    # Tournament management actions
    path('api/tournaments/<int:tournament_id>/open-registration/', api_tournaments.open_registration, name='open_registration'),
    path('api/tournaments/<int:tournament_id>/close-registration/', api_tournaments.close_registration, name='close_registration'),
    path('api/tournaments/<int:tournament_id>/cancel/', api_tournaments.cancel_tournament, name='cancel_tournament'),

    # Participant management
    path('api/tournaments/<int:tournament_id>/join/', api_tournaments.join_tournament, name='join_tournament'),
    path('api/tournaments/<int:tournament_id>/withdraw/', api_tournaments.withdraw_from_tournament, name='withdraw_from_tournament'),
    path('api/tournaments/<int:tournament_id>/approve-participant/', api_tournaments.approve_participant, name='approve_participant'),
    path('api/tournaments/<int:tournament_id>/confirm-participants/', api_tournaments.confirm_participants, name='confirm_participants'),

    # Bracket and match management
    path('api/tournaments/<int:tournament_id>/generate-bracket/', api_tournaments.generate_bracket, name='generate_bracket'),
    path('api/tournaments/<int:tournament_id>/bracket/', api_tournaments.get_bracket, name='get_bracket'),
    path('api/tournaments/<int:tournament_id>/start/', api_tournaments.start_tournament, name='start_tournament'),
    path('api/tournaments/<int:tournament_id>/finish/', api_tournaments.finish_tournament, name='finish_tournament'),
    path('api/tournament-matches/<int:match_id>/report-result/', api_tournaments.report_match_result, name='report_match_result'),

    # Users API (Sprint 4)
    path('api/users/', api_users.users_list, name='users_list'),

    # API (for mobile apps)
    # path('api/', include('v2_core.api_urls')),
]

# Media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += [path('__debug__/', include('debug_toolbar.urls'))]
