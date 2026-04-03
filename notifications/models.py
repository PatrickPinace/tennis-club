# notifications/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Notifications(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        db_table = 'notifications'

    def __str__(self):
        return f'Notification for {self.user.username}: {self.message[:50]}...'