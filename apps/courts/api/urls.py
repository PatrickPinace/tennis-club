from django.urls import path
from . import views

urlpatterns = [
    path('courts/reservations/', views.MyReservationListView.as_view(), name='my-reservations'),
    path('courts/reservations/pending/', views.PendingReservationsView.as_view(), name='reservations-pending'),
    path('courts/reservations/<int:pk>/', views.CancelReservationView.as_view(), name='my-reservation-cancel'),
    path('courts/reservations/<int:pk>/status/', views.ReservationStatusView.as_view(), name='reservation-status'),
    path('courts/series/<uuid:series_uuid>/', views.CancelSeriesView.as_view(), name='cancel-series'),
    path('courts/facilities/', views.FacilityListView.as_view(), name='courts-facilities'),
    path('courts/timeline/<int:facility_pk>/', views.TimelineView.as_view(), name='courts-timeline'),
    path('courts/reserve/', views.CreateReservationView.as_view(), name='courts-reserve'),
]
