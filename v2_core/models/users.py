"""User profiles and extensions."""
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    """Rozszerzenie profilu u|ytkownika."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    birth_date = models.DateField(null=True, blank=True)
    city = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    image = models.ImageField(upload_to='profile_pics', default='default.png', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Ranking fields
    elo_rating = models.IntegerField(default=1200, help_text='Rating Elo gracza')
    ranking_points = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Punkty rankingowe z turniejów'
    )

    class Meta:
        db_table = 'profiles'
        verbose_name = 'Profil'
        verbose_name_plural = 'Profile'
        indexes = [
            models.Index(fields=['-elo_rating']),
            models.Index(fields=['-ranking_points']),
        ]

    def __str__(self):
        return f'{self.user.username} Profile'


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatycznie tworzy profil przy tworzeniu u|ytkownika."""
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Zapisuje profil przy zapisie u|ytkownika."""
    instance.profile.save()
