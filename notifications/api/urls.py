from django.urls import path
from . import views

urlpatterns = [
    path('notifications/', views.NotificationListView.as_view(), name='notification-list'),
    path('notifications/list/', views.NotificationListView.as_view(), name='notification-list-legacy'),
    path('notifications/<int:pk>/read/', views.NotificationMarkReadView.as_view(), name='notification-read'),
    path('notifications/read-all/', views.NotificationMarkAllReadView.as_view(), name='notification-read-all'),
    path('notifications/seen/', views.NotificationSeenView.as_view(), name='notification-seen'),
    path('notifications/preferences/', views.NotificationPreferencesView.as_view(), name='notification-preferences'),
]
