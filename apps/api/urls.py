from django.urls import path, include

urlpatterns = [
    path('', include('apps.tournaments.api.urls')),
    path('', include('apps.matches.api.urls')),
    path('', include('apps.users.api.urls')),
    path('', include('apps.rankings.api.urls')),
    path('', include('apps.home.api.urls')),
    path('', include('notifications.api.urls')),
    path('', include('chats.api.urls')),
    path('', include('apps.courts.api.urls')),
]