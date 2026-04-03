# models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from encrypted_model_fields.fields import EncryptedCharField

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    birth_date = models.DateField(null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    image = models.ImageField(default='default.png', upload_to='profile_pics', blank=True)
    garmin_login = models.CharField(max_length=100, null=True, blank=True)
    garmin_password = EncryptedCharField(max_length=100, null=True, blank=True)

    GARMIN_SYNC_TENNIS_ONLY = 'TENNIS_ONLY'
    GARMIN_SYNC_ALL = 'ALL'
    GARMIN_SYNC_CHOICES = [
        (GARMIN_SYNC_TENNIS_ONLY, 'Tylko aktywności tenisowe'),
        (GARMIN_SYNC_ALL, 'Wszystkie aktywności'),
    ]
    garmin_sync_option = models.CharField(
        max_length=20,
        choices=GARMIN_SYNC_CHOICES,
        default=GARMIN_SYNC_TENNIS_ONLY,
        help_text="Wybierz, które aktywności synchronizować z Garmin Connect.")

    def __str__(self):
        return f'{self.user.username} Profile'

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
