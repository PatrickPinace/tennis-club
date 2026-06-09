from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from notifications.models import Notifications, NotificationPreference
from notifications.api.serializers import NotificationSerializer
from notifications.preferences import PREFERENCE_GROUPS, group_key_for_event


class NotificationListView(APIView):
    """
    GET /api/notifications/
    Zwraca listę powiadomień + last_seen_at z profilu użytkownika.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Notifications.objects.filter(user=request.user).order_by('-created_at')
        serializer = NotificationSerializer(qs, many=True)
        last_seen_at = None
        profile = getattr(request.user, 'profile', None)
        if profile and profile.notifications_last_seen_at:
            last_seen_at = profile.notifications_last_seen_at.isoformat()
        return Response({
            'notifications': serializer.data,
            'last_seen_at': last_seen_at,
        })


class NotificationSeenView(APIView):
    """
    POST /api/notifications/seen/
    Ustawia notifications_last_seen_at = now() dla zalogowanego użytkownika.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = getattr(request.user, 'profile', None)
        if profile is None:
            return Response({'detail': 'Brak profilu.'}, status=status.HTTP_400_BAD_REQUEST)
        now = timezone.now()
        profile.notifications_last_seen_at = now
        profile.save(update_fields=['notifications_last_seen_at'])
        return Response({'last_seen_at': now.isoformat()})


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
