from django.urls import path
from . import views

urlpatterns = [
    path("privacy-policy/", views.privacy_policy, name="privacy_policy"),
    path("", views.home, name="home"),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('about-author/', views.about_author, name='about_author'),
]