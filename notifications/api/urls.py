from django.urls import path
from . import views

urlpatterns = [
    path('notifications/list/', views.NotificationListView.as_view(), name='notification-list'),
    path('notifications/<int:pk>/read/', views.NotificationMarkReadView.as_view(), name='notification-read'),
    path('notifications/read-all/', views.NotificationMarkAllReadView.as_view(), name='notification-read-all'),
]
