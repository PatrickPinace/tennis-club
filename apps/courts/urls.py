from django.urls import path
from . import views

app_name = 'courts'
urlpatterns = [
    path('', views.facility_list, name='facility-list'),
    path('reservations/', views.reservations, name='reservations'),
    path('<int:pk>/', views.redirect_to_reservations, name='facility-detail'),
    path('reserve/', views.redirect_to_reservations, name='create-reservation'),
    path('api/timeline-data/<int:pk>/', views.redirect_to_reservations, name='api-timeline-data'),
    path('add-facility/', views.redirect_to_reservations, name='create-facility'),
    path('<int:pk>/edit/', views.redirect_to_reservations, name='update-facility'),
    path('facility/<int:facility_pk>/add-court/', views.redirect_to_reservations, name='create-court'),
    path('court/<int:pk>/edit/', views.redirect_to_reservations, name='update-court'),
    path('reservation/<int:pk>/confirm/', views.redirect_to_reservations, name='confirm-reservation'),
    path('reservation/<int:pk>/propose-change/', views.redirect_to_reservations, name='propose-change-reservation'),
    path('reservation/<int:pk>/reject/', views.redirect_to_reservations, name='reject-reservation'),
    path('reservation/<int:pk>/delete/', views.redirect_to_reservations, name='delete-reservation'),
    path('reservation/<int:pk>/mark-changed/', views.redirect_to_reservations, name='mark-changed-reservation'),
]