from django.db import models

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
