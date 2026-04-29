from django.db import models
from django.conf import settings

class TennisFacility(models.Model):
    """Model reprezentujący obiekt tenisowy."""
    SURFACE_CHOICES = [
        ('Clay', 'Mączka'),
        ('Hard', 'Twarda'),
        ('Grass', 'Trawa'),
        ('Carpet', 'Dywanowa'),
    ]
    name = models.CharField(max_length=200, verbose_name="Nazwa obiektu")
    address = models.CharField(max_length=300, verbose_name="Adres")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Właściciel")
    description = models.TextField(blank=True, verbose_name="Opis")
    contact_phone = models.CharField(max_length=20, blank=True, verbose_name="Telefon kontaktowy")
    surface = models.CharField(max_length=10, choices=SURFACE_CHOICES, verbose_name="Nawierzchnia", default='Clay')
    image = models.ImageField(upload_to='facility_images/', blank=True, null=True, verbose_name="Zdjęcie obiektu")
    reservation = models.BooleanField(default=False, verbose_name="System rezerwacji")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Obiekt tenisowy"
        verbose_name_plural = "Obiekty tenisowe"

class Court(models.Model):
    """Model reprezentujący pojedynczy kort w obiekcie."""
    SURFACE_CHOICES = [
        ('Clay', 'Mączka'),
        ('Hard', 'Twarda'),
        ('Grass', 'Trawa'),
        ('Carpet', 'Dywanowa'),
    ]
    facility = models.ForeignKey(TennisFacility, related_name='courts', on_delete=models.CASCADE, verbose_name="Obiekt")
    court_number = models.PositiveIntegerField(verbose_name="Numer kortu")
    surface = models.CharField(max_length=10, choices=SURFACE_CHOICES, verbose_name="Nawierzchnia")
    is_indoor = models.BooleanField(default=False, verbose_name="Kort kryty")

    def __str__(self):
        return f"Kort nr {self.court_number} w {self.facility.name}"

    class Meta:
        verbose_name = "Kort"
        verbose_name_plural = "Korty"
        unique_together = ('facility', 'court_number')

class Reservation(models.Model):
    """Model reprezentujący rezerwację kortu."""
    STATUS_CHOICES = [
        ('PENDING', 'Oczekuje na zatwierdzenie'),
        ('CONFIRMED', 'Zatwierdzona'),
        ('REJECTED', 'Wymaga zmiany terminu'),
        ('CHANGED', 'Oczekuje na potwierdzenie zmiany terminu'),
    ]

    court = models.ForeignKey(Court, related_name='reservations', on_delete=models.CASCADE, null=True, blank=True, verbose_name="Kort")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Użytkownik")
    start_time = models.DateTimeField(verbose_name="Czas rozpoczęcia")
    end_time = models.DateTimeField(verbose_name="Czas zakończenia")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING', verbose_name="Status")

    def __str__(self):
        return f"Rezerwacja {self.court} przez {self.user} od {self.start_time} do {self.end_time}"

    class Meta:
        ordering = ['start_time']