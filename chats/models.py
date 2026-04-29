from django.conf import settings
from django.db import models
from django.db.models import Q

class ChatMessageManager(models.Manager):
    """
    Niestandardowy menedżer dla modelu ChatMessage.
    """
    def get_conversation(self, user1, user2):
        """
        Pobiera całą konwersację między dwoma użytkownikami,
        posortowaną od najstarszej do najnowszej wiadomości.

        Args:
            user1: Pierwszy użytkownik (obiekt User).
            user2: Drugi użytkownik (obiekt User).

        Returns:
            QuerySet zawierający wiadomości między dwoma użytkownikami.
        """
        return self.get_queryset().filter(
            (Q(sender=user1) & Q(recipient=user2)) |
            (Q(sender=user2) & Q(recipient=user1))
        ).order_by('timestamp')

class ChatMessage(models.Model):
    """
    Model reprezentujący pojedynczą wiadomość na czacie.
    """
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages', verbose_name="Nadawca"
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_messages', verbose_name="Odbiorca"
    )
    content = models.TextField(verbose_name="Treść", blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Znacznik czasu")
    is_read = models.BooleanField(default=False, verbose_name="Przeczytana")

    objects = ChatMessageManager()

    class Meta:
        ordering = ['timestamp']
        verbose_name = "Wiadomość na czacie"
        verbose_name_plural = "Wiadomości na czacie"

    def __str__(self):
        return f"Wiadomość od {self.sender} do {self.recipient} o {self.timestamp:%Y-%m-%d %H:%M}"

def chat_image_upload_path(instance, filename):
    """Generuje ścieżkę zapisu dla obrazka w czacie."""
    return f'chat_images/{instance.message.id}/{filename}'

class ChatImage(models.Model):
    """
    Model reprezentujący obrazek wysłany w wiadomości na czacie.
    """
    message = models.ForeignKey(
        ChatMessage, on_delete=models.CASCADE, related_name='images', verbose_name="Wiadomość"
    )
    image = models.ImageField(upload_to=chat_image_upload_path, verbose_name="Obrazek")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Data wgrania")

    class Meta:
        ordering = ['uploaded_at']
        verbose_name = "Obrazek w wiadomości"
        verbose_name_plural = "Obrazki w wiadomościach"

    def __str__(self):
        return f"Obrazek do wiadomości {self.message.id} z {self.uploaded_at:%Y-%m-%d %H:%M}"

# --- Modele dla czatu meczowego (grupowego) ---

class TournamentMatchChatMessage(models.Model):
    """
    Model reprezentujący pojedynczą wiadomość na czacie meczowym.
    """
    match = models.ForeignKey(
        'tournaments.TournamentsMatch', on_delete=models.CASCADE, related_name='chat_messages', verbose_name="Mecz"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='match_chat_messages', verbose_name="Nadawca"
    )
    content = models.TextField(verbose_name="Treść", blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Znacznik czasu")

    class Meta:
        ordering = ['timestamp']
        verbose_name = "Wiadomość na czacie meczowym"
        verbose_name_plural = "Wiadomości na czacie meczowym"

    def __str__(self):
        return f"Wiadomość w meczu {self.match.id} od {self.sender} o {self.timestamp:%Y-%m-%d %H:%M}"

def tournament_match_chat_image_upload_path(instance, filename):
    """Generuje ścieżkę zapisu dla obrazka w czacie meczowym."""
    return f'tournament_chat_images/{instance.message.match.id}/{instance.message.id}/{filename}'

class TournamentMatchChatImage(models.Model):
    """
    Model reprezentujący obrazek wysłany w wiadomości na czacie meczowym.
    """
    message = models.ForeignKey(
        TournamentMatchChatMessage, on_delete=models.CASCADE, related_name='images', verbose_name="Wiadomość"
    )
    image = models.ImageField(upload_to=tournament_match_chat_image_upload_path, verbose_name="Obrazek")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Data wgrania")

    class Meta:
        ordering = ['uploaded_at']
        verbose_name = "Obrazek w czacie meczowym"
        verbose_name_plural = "Obrazki w czacie meczowym"