from django.urls import path
from . import views

app_name = 'activities'

urlpatterns = [
    path("", views.activity_list, name="activity_list"),
    path("sync/", views.sync_garmin_activities, name="garmin_sync"),
    path("force-sync/", views.force_garmin_sync, name="force_garmin_sync"),
    path("disconnect/", views.garmin_disconnect, name="garmin_disconnect"),
    path("<int:activity_id>/delete/", views.delete_activity, name="activity_delete"),
    path("<int:activity_id>/resync/", views.resync_activity, name="activity_resync"),
    path("<int:activity_id>/edit/", views.edit_activity_name, name="activity_edit_name"),
    # Ten wzorzec musi być na końcu, aby nie przechwytywać innych ścieżek, jak 'sync'
    path("<int:activity_id>/", views.activity_detail, name="activity_detail"),
]
