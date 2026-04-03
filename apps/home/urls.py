from django.urls import path
from . import views
from .views import home, PrivacyPolicyView

urlpatterns = [
    path("privacy-policy/", PrivacyPolicyView.as_view(), name="privacy_policy"),
    path("", home, name="home"),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('about-author/', views.about_author, name='about_author'),
]