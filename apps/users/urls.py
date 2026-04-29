# users/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("edit/profile/", views.users_edit, name="users_edit"),
    path('login/', views.users_login, name='login'),
    path("logout/", views.users_logout, name="logout"),
    path('register/', views.users_register, name='register'),
    # Własny widok zmiany hasła
    path("password/change/", views.change_password, name="change_password"),
]
