from django.urls import path
from . import views

urlpatterns = [
    path('rankings/list/', views.RankingListView.as_view(), name='ranking-list'),
    path('rankings/seasons/', views.RankingSeasonsView.as_view(), name='ranking-seasons'),
    path('rankings/info/', views.RankingCalculationInfoView.as_view(), name='ranking-info'),
    path('admin/rebuild-rankings/', views.RebuildRankingsView.as_view(), name='rebuild-rankings'),
]
