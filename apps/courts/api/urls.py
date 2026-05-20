from django.urls import path
from . import views

urlpatterns = [
    path('courts/reservations/', views.MyReservationListView.as_view(), name='my-reservations'),
    path('courts/facilities/', views.FacilityListView.as_view(), name='courts-facilities'),
    path('courts/timeline/<int:facility_pk>/', views.TimelineView.as_view(), name='courts-timeline'),
    path('courts/reserve/', views.CreateReservationView.as_view(), name='courts-reserve'),
]
