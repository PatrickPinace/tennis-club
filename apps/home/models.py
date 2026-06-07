from django.db import models
from django.conf import settings

class BlockedPattern(models.Model):
    pattern = models.CharField(max_length=255, verbose_name="Wzorzec URL")
    description = models.TextField(blank=True, verbose_name="Opis (np. dlaczego blokujemy)")
    is_active = models.BooleanField(default=True, verbose_name="Aktywny")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data dodania")

    class Meta:
        verbose_name = "Zablokowany Wzorzec"
        verbose_name_plural = "Zablokowane Wzorce"
        ordering = ['-created_at']

    def __str__(self):
        return self.pattern


class LoginAttempt(models.Model):
    STATUS_CHOICES = [
        ('success', 'Sukces'),
        ('failed', 'Niepowodzenie'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Użytkownik"
    )
    username = models.CharField(max_length=255, db_index=True, verbose_name="Nazwa użytkownika")
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True, verbose_name="Adres IP")
    user_agent = models.TextField(blank=True, default="", verbose_name="User Agent")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, verbose_name="Status")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Czas zdarzenia")

    class Meta:
        verbose_name = "Próba logowania"
        verbose_name_plural = "Próby logowania"
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.username} - {self.status} ({self.timestamp})"

    @property
    def browser(self):
        ua = self.user_agent.lower() if self.user_agent else ""
        if 'firefox' in ua:
            return 'Firefox'
        elif 'chrome' in ua and 'safari' in ua and 'edge' not in ua and 'edg' not in ua:
            return 'Chrome'
        elif 'safari' in ua and 'chrome' not in ua:
            return 'Safari'
        elif 'edge' in ua or 'edg' in ua:
            return 'Edge'
        elif 'opera' in ua or 'opr' in ua:
            return 'Opera'
        elif 'msie' in ua or 'trident' in ua:
            return 'IE'
        return 'Inna'

    @property
    def device(self):
        ua = self.user_agent.lower() if self.user_agent else ""
        if 'ipad' in ua or 'tablet' in ua:
            return 'Tablet'
        elif 'mobile' in ua or 'iphone' in ua or 'android' in ua:
            return 'Mobile'
        return 'Desktop'


class PageView(models.Model):
    path = models.CharField(max_length=255, verbose_name="Ścieżka URL")
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True, verbose_name="Adres IP")
    user_agent = models.TextField(blank=True, default="", verbose_name="User Agent")
    method = models.CharField(max_length=10, default="GET", verbose_name="Metoda HTTP")
    session_key = models.CharField(max_length=40, null=True, blank=True, db_index=True, verbose_name="Klucz sesji")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Użytkownik"
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Czas wizyty")

    class Meta:
        verbose_name = "Odsłona strony"
        verbose_name_plural = "Statystyki aktywności"
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.path} - {self.ip_address} ({self.timestamp})"

    @property
    def browser(self):
        ua = self.user_agent.lower() if self.user_agent else ""
        if 'firefox' in ua:
            return 'Firefox'
        elif 'chrome' in ua and 'safari' in ua and 'edge' not in ua and 'edg' not in ua:
            return 'Chrome'
        elif 'safari' in ua and 'chrome' not in ua:
            return 'Safari'
        elif 'edge' in ua or 'edg' in ua:
            return 'Edge'
        elif 'opera' in ua or 'opr' in ua:
            return 'Opera'
        elif 'msie' in ua or 'trident' in ua:
            return 'IE'
        return 'Inny'

    @property
    def device(self):
        ua = self.user_agent.lower() if self.user_agent else ""
        if 'ipad' in ua or 'tablet' in ua:
            return 'Tablet'
        elif 'mobile' in ua or 'iphone' in ua or 'android' in ua:
            return 'Mobile'
        return 'Desktop'


