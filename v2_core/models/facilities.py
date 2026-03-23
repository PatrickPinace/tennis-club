"""Tennis facilities, courts and reservations."""
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class Facility(models.Model):
    """Obiekt tenisowy (klub, centrum)."""
    SURFACE_CHOICES = [
        ('clay', 'Mczka'),
        ('hard', 'Twarda'),
        ('grass', 'Trawa'),
        ('carpet', 'Dywanowa'),
    ]

    name = models.CharField(max_length=200)
    address = models.CharField(max_length=300)
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_facilities'
    )
    description = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    default_surface = models.CharField(
        max_length=10,
        choices=SURFACE_CHOICES,
        default='clay'
    )
    image = models.ImageField(upload_to='facility_images/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'facilities'
        verbose_name = 'Obiekt tenisowy'
        verbose_name_plural = 'Obiekty tenisowe'
        ordering = ['name']

    def __str__(self):
        return self.name


class Court(models.Model):
    """Kort tenisowy w obiekcie."""
    SURFACE_CHOICES = Facility.SURFACE_CHOICES

    facility = models.ForeignKey(
        Facility,
        on_delete=models.CASCADE,
        related_name='courts'
    )
    number = models.PositiveIntegerField(help_text='Numer kortu w obiekcie')
    surface = models.CharField(max_length=10, choices=SURFACE_CHOICES)
    is_indoor = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'courts'
        verbose_name = 'Kort'
        verbose_name_plural = 'Korty'
        unique_together = [['facility', 'number']]
        ordering = ['facility', 'number']

    def __str__(self):
        return f"Kort {self.number} - {self.facility.name}"


class Reservation(models.Model):
    """Rezerwacja kortu."""
    STATUS_CHOICES = [
        ('pending', 'Oczekuje'),
        ('confirmed', 'Potwierdzona'),
        ('cancelled', 'Anulowana'),
    ]

    court = models.ForeignKey(
        Court,
        on_delete=models.CASCADE,
        related_name='reservations'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reservations'
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'reservations'
        verbose_name = 'Rezerwacja'
        verbose_name_plural = 'Rezerwacje'
        ordering = ['start_time']
        indexes = [
            models.Index(fields=['court', 'start_time']),
            models.Index(fields=['user', '-start_time']),
            models.Index(fields=['status']),
        ]

    def clean(self):
        if self.end_time <= self.start_time:
            raise ValidationError('Czas koDca musi by pózniejszy ni| czas rozpoczcia.')

    def __str__(self):
        return f"{self.court} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"
