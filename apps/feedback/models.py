from django.db import models
from django.conf import settings

class Feedback(models.Model):
    class Status(models.TextChoices):
        NEW = 'NEW', 'Nowe'
        IN_PROGRESS = 'IN_PROGRESS', 'W trakcie'
        RESOLVED = 'RESOLVED', 'Rozwiązane'
        CLOSED = 'CLOSED', 'Zamknięte'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Użytkownik")
    subject = models.CharField(max_length=255, verbose_name="Temat")
    message = models.TextField(verbose_name="Wiadomość")
    email = models.EmailField(verbose_name="Adres e-mail (opcjonalnie)", max_length=254, blank=True, null=True)
    url = models.URLField(max_length=2048, verbose_name="URL zgłoszenia", blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data zgłoszenia")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        verbose_name="Status"
    )
    ip_address = models.GenericIPAddressField(verbose_name="Adres IP", null=True, blank=True)

    def __str__(self):
        return f"Zgłoszenie od {self.user.username if self.user else 'Anonim'} - {self.subject}"

    class Meta:
        verbose_name = "Zgłoszenie"
        verbose_name_plural = "Zgłoszenia"
        ordering = ['-created_at']