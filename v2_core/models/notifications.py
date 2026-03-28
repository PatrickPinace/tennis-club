"""User notifications."""
from django.db import models
from django.contrib.auth.models import User


class Notification(models.Model):
    """Powiadomienie dla użytkownika."""
    TYPE_CHOICES = [
        ('info', 'Informacja'),
        ('match', 'Mecz'),
        ('tournament', 'Turniej'),
        ('reservation', 'Rezerwacja'),
        ('system', 'System'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='info'
    )
    title = models.CharField(max_length=100)
    message = models.TextField()

    # Link (optional)
    link = models.CharField(
        max_length=200,
        blank=True,
        help_text='URL do przekierowania po kliknięciu'
    )

    # Status
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        verbose_name = 'Powiadomienie'
        verbose_name_plural = 'Powiadomienia'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read']),
        ]

    def __str__(self):
        return f"{self.user.username}: {self.title}"
