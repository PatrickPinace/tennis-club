from django.urls import path
from .views import InboxView, ConversationView, CheckNewMessagesView, CheckNewMatchMessagesView

app_name = 'chats'

urlpatterns = [
    path('', InboxView.as_view(), name='inbox'),
    path('<str:username>/', ConversationView.as_view(), name='conversation'),
    path('api/check-new/<str:username>/', CheckNewMessagesView.as_view(), name='check_new_messages'),
    path('api/match-check-new/<int:match_pk>/', CheckNewMatchMessagesView.as_view(), name='match_check_new_messages'),
]