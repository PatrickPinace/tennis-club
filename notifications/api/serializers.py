from rest_framework import serializers
from notifications.models import Notifications

class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for notifications."""
    class Meta:
        model = Notifications
        fields = ('id', 'message', 'created_at', 'is_read', 'target_url')
