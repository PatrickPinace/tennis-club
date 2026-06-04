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
    image = models.ImageField(default='default.png', upload_to='profile_pics', blank=True)

    def __str__(self):
        return f'{self.user.username} Profile'

class PasswordResetToken(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_tokens')
    token      = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Token resetu hasła'

    def __str__(self):
        return f'PasswordResetToken({self.user.username}, expires={self.expires_at})'


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def send_welcome_email(sender, instance, created, **kwargs):
    if created and instance.email:
        from apps.utils.email_service import send_notification_email
        subject = "Witaj w Klubie Tenisa Ziemnego!"
        message = f"Witaj {instance.username},\n\nDziękujemy za założenie konta w naszym klubie."
        send_notification_email(
            subject=subject,
            message=message,
            recipient_list=[instance.email]
        )

