"""
API URLs for authentication endpoints
Used by Astro frontend
"""
from django.urls import path
from . import api_views

app_name = 'users_api'

urlpatterns = [
    path('login/', api_views.api_login, name='api_login'),
    path('logout/', api_views.api_logout, name='api_logout'),
    path('me/', api_views.api_current_user, name='api_current_user'),
    path('profile/', api_views.api_user_profile, name='api_user_profile'),
    path('csrf/', api_views.get_csrf_token, name='get_csrf_token'),
]
