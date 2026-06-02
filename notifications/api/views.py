from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from notifications.models import Notifications, NotificationPreference
from notifications.api.serializers import NotificationSerializer
from notifications.preferences import PREFERENCE_GROUPS, group_key_for_event

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


class NotificationPreferencesView(APIView):
    """
    GET  /api/notifications/preferences/  — zwraca stan preferencji (5 grup)
    PATCH /api/notifications/preferences/ — aktualizuje wybrane grupy

    Default (brak rekordu w DB) = włączone.
    Body PATCH: { "reservations": false, "ladder": true, ... }
    """
    permission_classes = [IsAuthenticated]

    def _get_state(self, user):
        """Zwraca słownik {group_key: is_enabled} dla wszystkich grup."""
        # Pobierz wszystkie istniejące preferencje usera dla inapp
        existing = {
            p.event_type: p.is_enabled
            for p in NotificationPreference.objects.filter(user=user, channel='inapp')
        }
        result = []
        for group in PREFERENCE_GROUPS:
            # Grupa jest wyłączona jeśli WSZYSTKIE event_types są off; włączona w pozostałych
            # Ale prościej: jeden rekord na grupę przechowujemy jako event_type=group.key (canonical)
            # Canonical event_type dla grupy = pierwszy z listy event_types w grupie
            canonical = group['event_types'][0]
            enabled = existing.get(canonical, True)  # default True jeśli brak
            result.append({
                'key': group['key'],
                'label': group['label'],
                'description': group['description'],
                'enabled': enabled,
            })
        return result

    def get(self, request):
        return Response(self._get_state(request.user))

    def patch(self, request):
        valid_keys = {g['key'] for g in PREFERENCE_GROUPS}
        groups_by_key = {g['key']: g for g in PREFERENCE_GROUPS}

        errors = {}
        for key, value in request.data.items():
            if key not in valid_keys:
                errors[key] = 'Nieznana kategoria preferencji.'
                continue
            if not isinstance(value, bool):
                errors[key] = 'Wartość musi być true lub false.'
                continue

        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        for key, enabled in request.data.items():
            if key not in valid_keys:
                continue
            group = groups_by_key[key]
            # Zapisz preferencję per canonical event_type (pierwszy z grupy)
            canonical = group['event_types'][0]
            NotificationPreference.objects.update_or_create(
                user=request.user,
                event_type=canonical,
                channel='inapp',
                defaults={'is_enabled': bool(enabled)},
            )

        return Response(self._get_state(request.user))
