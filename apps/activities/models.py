from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse

# Importy potrzebne do GenericForeignKey
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class Activity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='garmin_activities')
    
    # Pola dla GenericForeignKey, które zastępują stary klucz obcy 'match'
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Typ obiektu meczu")
    object_id = models.PositiveIntegerField(null=True, blank=True, verbose_name="ID obiektu meczu")
    content_object = GenericForeignKey('content_type', 'object_id')

    activity_id = models.BigIntegerField(unique=True)
    activity_name = models.CharField(max_length=255)
    activity_type_key = models.CharField(max_length=50, null=True, blank=True, help_text="Klucz typu aktywności z Garmin, np. 'tennis_v2'")
    start_time = models.DateTimeField(db_index=True)
    duration = models.FloatField(help_text="In seconds")
    distance = models.FloatField(help_text="In meters")
    average_hr = models.IntegerField(null=True, blank=True)
    max_hr = models.IntegerField(null=True, blank=True)
    calories = models.IntegerField(null=True, blank=True)
    tennis_data_fetched = models.BooleanField(default=False, help_text="Czy dane z aplikacji Tennis Studio zostały pomyślnie pobrane")

    def __str__(self):
        return f"{self.activity_name} ({self.user.username})"

    def get_absolute_url(self):
        return reverse('activities:activity_detail', kwargs={'activity_id': self.activity_id})

    @property
    def duration_in_minutes(self):
        if self.duration:
            return self.duration / 60
        return 0

    @property
    def distance_in_km(self):
        if self.distance:
            return self.distance / 1000
        return 0


class TennisData(models.Model):
    """Przechowuje dodatkowe dane deweloperskie z aktywności tenisowej (np. z aplikacji Tennis Studio)."""
    activity = models.OneToOneField(Activity, on_delete=models.CASCADE, related_name='tennis_data')

    owner_stats_side = models.CharField(max_length=1, choices=[('L', 'Left'), ('P', 'Right')], null=True, blank=True, help_text="Indicates if the activity owner's stats are on the 'Left' or 'Right' side of the Garmin data.")

    score = models.CharField(max_length=50, null=True, blank=True, help_text="Wynik meczu, np. 6-4 6-3")
    points = models.CharField(max_length=50, null=True, blank=True, help_text="Zdobyte punkty (np. w formacie '55:25')")
    serving_points = models.CharField(max_length=50, null=True, blank=True, help_text="Punkty przy serwisie")
    aces = models.CharField(max_length=50, null=True, blank=True, help_text="Asy serwisowe")
    double_faults = models.CharField(max_length=50, null=True, blank=True, help_text="Podwójne błędy")
    first_serve_percentage = models.CharField(max_length=50, null=True, blank=True, help_text="Procent pierwszego serwisu")
    win_percentage_on_first_serve = models.CharField(max_length=50, null=True, blank=True, help_text="Procent wygranych po 1. serwisie")
    win_percentage_on_second_serve = models.CharField(max_length=50, null=True, blank=True, help_text="Procent wygranych po 2. serwisie")
    receiving_points = models.CharField(max_length=50, null=True, blank=True, help_text="Punkty przy odbiorze")
    games = models.CharField(max_length=50, null=True, blank=True, help_text="Gemy (np. w formacie '12 : 2')")
    breakpoints = models.CharField(max_length=50, null=True, blank=True, help_text="Punkty przełamania (np. w formacie '5/9 : 0/0')")
    set_points = models.CharField(max_length=50, null=True, blank=True, help_text="Piłki setowe")
    match_points = models.CharField(max_length=50, null=True, blank=True, help_text="Piłki meczowe")
    sets_durations = models.CharField(max_length=100, null=True, blank=True, help_text="Czasy trwania setów")
    winners = models.CharField(max_length=50, null=True, blank=True, help_text="Uderzenia wygrywające")
    unforced_errors = models.CharField(max_length=50, null=True, blank=True, help_text="Niewymuszone błędy")

    def __str__(self):
        return f"Dane tenisa dla aktywności: {self.activity.activity_name}"
