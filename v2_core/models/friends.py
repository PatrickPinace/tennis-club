"""Friends and friend requests."""
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Q, F
from django.db.models.functions import Least, Greatest


class Friendship(models.Model):
    """Relacja znajomości między użytkownikami."""
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

    def clean(self):
        """Walidacja - blokuje self-relation."""
        if self.user_id and self.friend_id and self.user_id == self.friend_id:
            raise ValidationError("Nie można dodać siebie do znajomych.")

    def save(self, *args, **kwargs):
        """Normalizacja pary - zawsze user_id < friend_id."""
        if self.user_id and self.friend_id and self.user_id > self.friend_id:
            self.user_id, self.friend_id = self.friend_id, self.user_id
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        db_table = 'friendships'
        verbose_name = 'Znajomość'
        verbose_name_plural = 'Znajomości'
        ordering = ['-created_at']
        constraints = [
            # Blokuje self-relation (A,A)
            models.CheckConstraint(
                condition=~Q(user=F('friend')),
                name='friendships_no_self_relation'
            ),
            # Blokuje odwrócone duplikaty (A,B) i (B,A)
            models.UniqueConstraint(
                Least('user_id', 'friend_id'),
                Greatest('user_id', 'friend_id'),
                name='friendships_unique_normalized_pair'
            ),
        ]
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['friend']),
        ]

    def __str__(self):
        return f"{self.user.username} ↔ {self.friend.username}"


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
        return f"{self.sender.username} → {self.receiver.username} ({self.status})"
