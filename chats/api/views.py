from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from chats.models import ChatMessage

class UnreadChatMessagesCountView(APIView):
    """Returns the count of unread chat conversations for the user."""
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        count = ChatMessage.objects.filter(recipient=request.user, is_read=False).values('sender').distinct().count()
        return Response({'unread_count': count}, status=status.HTTP_200_OK)
