from django.db import models
from django.contrib.auth.models import User
from django.db.models import UniqueConstraint
class Friend(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="friends")
    friend = models.ForeignKey(User, on_delete=models.CASCADE, related_name="friend_of")

    class Meta:
        db_table = "user_friend"
        constraints = [
            UniqueConstraint(fields=['user', 'friend'], name='unique_friend')
        ]

    def __str__(self):
        return f"{self.user.username} -> {self.friend.username}"


class FriendRequest(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_friend_requests")
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_friend_requests")
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='pending')  # 'pending', 'accepted', 'rejected'

    class Meta:
        db_table = "friend_request"
        unique_together = ('sender', 'receiver')  # Użytkownik może wysłać tylko jedno zaproszenie do drugiego użytkownika

    def __str__(self):
        return f"Request from {self.sender.username} to {self.receiver.username} ({self.status})"