from django.urls import path
from . import views

app_name = 'matches'

urlpatterns = [
    path('results/', views.results, name='matches_results'),
    path('summary/', views.summary, name='matches_summary'),
    path('results/remove/<int:match_id>/', views.remove_match, name='matches_remove'),
    path('add/match/', views.add_match, name='matches_add_match'),
    path('edit/match/<int:match_id>/', views.edit_match, name='matches_edit_match'),
    path('<str:match_id>/', views.match_detail, name='match_detail'),
    path('<str:match_id>/assign_activity/', views.assign_activity, name='assign_activity'),
]
