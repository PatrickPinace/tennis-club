from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from notifications.models import Notifications
from notifications.api.serializers import NotificationSerializer

class NotificationListView(generics.ListAPIView):
    """API endpoint that lists notifications for the current user."""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notifications.objects.filter(user=self.request.user)


class NotificationMarkReadView(APIView):
    """
    PATCH /api/notifications/{pk}/read/
    Oznacza pojedyncze powiadomienie jako przeczytane.
    Tylko właściciel może oznaczyć swoje powiadomienie.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            notif = Notifications.objects.get(pk=pk, user=request.user)
        except Notifications.DoesNotExist:
            return Response({'detail': 'Nie znaleziono.'}, status=status.HTTP_404_NOT_FOUND)
        notif.is_read = True
        notif.save(update_fields=['is_read'])
        return Response({'id': notif.pk, 'is_read': True}, status=status.HTTP_200_OK)


class NotificationMarkAllReadView(APIView):
    """
    POST /api/notifications/read-all/
    Oznacza wszystkie powiadomienia użytkownika jako przeczytane.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated = Notifications.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'marked': updated}, status=status.HTTP_200_OK)
