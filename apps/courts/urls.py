from django.urls import path
from . import views

app_name = 'courts'
urlpatterns = [
    path('', views.FacilityListView.as_view(), name='facility-list'),
    path('reservations/', views.ReservationFacilityListView.as_view(), name='reservations'),
    path('<int:pk>/', views.FacilityDetailView.as_view(), name='facility-detail'),
    path('reserve/', views.CreateReservationView.as_view(), name='create-reservation'),
    path('api/timeline-data/<int:pk>/', views.TimelineDataView.as_view(), name='api-timeline-data'),
    path('add-facility/', views.CreateFacilityView.as_view(), name='create-facility'),
    path('<int:pk>/edit/', views.UpdateFacilityView.as_view(), name='update-facility'),
    path('facility/<int:facility_pk>/add-court/', views.CourtCreateView.as_view(), name='create-court'),
    path('court/<int:pk>/edit/', views.CourtUpdateView.as_view(), name='update-court'),
    path('reservation/<int:pk>/confirm/', views.UpdateReservationStatusView.as_view(), {'status': 'CONFIRMED'}, name='confirm-reservation'),
    path('reservation/<int:pk>/propose-change/', views.UpdateReservationStatusView.as_view(), {'status': 'REJECTED'}, name='propose-change-reservation'),
    path('reservation/<int:pk>/reject/', views.UpdateReservationStatusView.as_view(), {'status': 'REJECTED'}, name='reject-reservation'),
    path('reservation/<int:pk>/delete/', views.DeleteReservationView.as_view(), name='delete-reservation'),
    path('reservation/<int:pk>/mark-changed/', views.UpdateReservationStatusView.as_view(), {'status': 'CHANGED'}, name='mark-changed-reservation'),
]