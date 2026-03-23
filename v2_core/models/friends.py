"""Friends and friend requests."""
from django.db import models
from django.contrib.auth.models import User


class Friendship(models.Model):
    """Relacja znajomo[ci midzy u|ytkownikami."""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='friendships'
    )
    friend = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='friend_of'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'friendships'
        verbose_name = 'Znajomo['
        verbose_name_plural = 'Znajomo[ci'
        unique_together = [['user', 'friend']]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} ” {self.friend.username}"


class FriendRequest(models.Model):
    """Zaproszenie do znajomych."""
    STATUS_CHOICES = [
        ('pending', 'Oczekuje'),
        ('accepted', 'Zaakceptowane'),
        ('rejected', 'Odrzucone'),
    ]

    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_friend_requests'
    )
    receiver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='received_friend_requests'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'friend_requests'
        verbose_name = 'Zaproszenie do znajomych'
        verbose_name_plural = 'Zaproszenia do znajomych'
        unique_together = [['sender', 'receiver']]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.sender.username} ’ {self.receiver.username} ({self.status})"
