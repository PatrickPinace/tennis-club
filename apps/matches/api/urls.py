from django.urls import path
from . import views

urlpatterns = [
    path('matches/create/', views.MatchCreateView.as_view(), name='match-create'),
    path('matches/<int:pk>/', views.MatchDetailView.as_view(), name='match-detail'),
    path('matches/<int:pk>/confirm/', views.MatchConfirmView.as_view(), name='match-confirm'),
    path('matches/history/', views.MatchHistoryView.as_view(), name='match-history'),
    path('matches/filters/', views.MatchFiltersView.as_view(), name='match-filters'),
]
