from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='api-register'),
    path('users/', views.UserListView.as_view(), name='user-list'),
    path('users/me/', views.UserDetailsView.as_view(), name='user-details'),
]
