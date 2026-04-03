from django.urls import path
from . import views

app_name = 'feedback'
urlpatterns = [
    path('submit/', views.submit_feedback, name='submit_feedback'),
    path('update-status/<int:feedback_id>/', views.UpdateFeedbackStatusView.as_view(), name='update_feedback_status'),
    path('manage/', views.FeedbackListView.as_view(), name='manage_feedback'),
]