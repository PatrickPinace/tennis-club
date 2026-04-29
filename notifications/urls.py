# notifications/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('api/vapid-public-key/', views.get_vapid_public_key, name='get_vapid_public_key'),
    path('api/save-subscription/', views.save_subscription, name='save_subscription'),
    path('api/notifications/', views.get_notifications, name='get_notifications'),
    path('api/unread-count/', views.get_unread_count, name='unread_count'),
    path('api/notifications/read_all/', views.read_all_notifications, name='read_all_notifications'),
]