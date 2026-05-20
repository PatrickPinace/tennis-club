from django.urls import path
from . import views

urlpatterns = [
    path('rankings/list/', views.RankingListView.as_view(), name='ranking-list'),
    path('admin/rebuild-rankings/', views.RebuildRankingsView.as_view(), name='rebuild-rankings'),
]
