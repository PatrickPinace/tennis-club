# notifications/models.py
from django.db import models
from django.contrib.auth.models import User


EVENT_TYPES = (
    ('generic', 'Ogólne'),
    ('court.reservation.created', 'Nowa rezerwacja kortu'),
    ('court.reservation.accepted', 'Rezerwacja zaakceptowana'),
    ('court.reservation.rejected', 'Rezerwacja odrzucona'),
    ('court.reservation.cancelled', 'Rezerwacja anulowana'),
    ('tournament.created', 'Turniej utworzony'),
    ('tournament.started', 'Turniej rozpoczęty'),
    ('tournament.finished', 'Turniej zakończony'),
    ('tournament.cancelled', 'Turniej anulowany'),
    ('tournament.participant.added', 'Dodano uczestnika'),
    ('tournament.match.score_entered', 'Wynik meczu wpisany'),
    ('tournament.match.walkover', 'Walkover'),
    ('tournament.ladder.challenge_sent', 'Wyzwanie wysłane'),
    ('tournament.ladder.challenge_accepted', 'Wyzwanie zaakceptowane'),
    ('tournament.ladder.challenge_rejected', 'Wyzwanie odrzucone'),
    ('tournament.participant.joined', 'Uczestnik dołączył samodzielnie'),
    ('tournament.participant.removed', 'Uczestnik wycofany przez organizatora'),
)

CHANNEL_CHOICES = (
    ('inapp', 'In-app'),
    ('email', 'Email'),
    ('sms', 'SMS'),
)

DELIVERY_STATUS_CHOICES = (
    ('pending', 'Oczekujące'),
    ('sent', 'Wysłane'),
    ('delivered', 'Dostarczone'),
    ('failed', 'Błąd dostarczenia'),
)


class Notifications(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    target_url = models.CharField(max_length=500, null=True, blank=True)
    event_type = models.CharField(
        max_length=50, choices=EVENT_TYPES, default='generic', blank=True
    )
    channel = models.CharField(
        max_length=20, choices=CHANNEL_CHOICES, default='inapp'
    )
    delivery_status = models.CharField(
        max_length=20, choices=DELIVERY_STATUS_CHOICES, default='pending'
    )
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'notifications'
        verbose_name = "Powiadomienie"
        verbose_name_plural = "Powiadomienia"

    def __str__(self):
        return f'Notification for {self.user.username}: {self.message[:50]}...'


class NotificationPreference(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='notification_preferences'
    )
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='inapp')
    is_enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ('user', 'event_type', 'channel')
        ordering = ['event_type', 'channel']
        verbose_name = "Preferencja powiadomień"
        verbose_name_plural = "Preferencje powiadomień"

    def __str__(self):
        status = 'on' if self.is_enabled else 'off'
        return f'{self.user.username} | {self.event_type} | {self.channel} = {status}'
