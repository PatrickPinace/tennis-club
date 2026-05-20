from django.urls import path
from . import views

urlpatterns = [
    path('chats/unread-count/', views.UnreadChatMessagesCountView.as_view(), name='unread-chat-messages-count'),
]
