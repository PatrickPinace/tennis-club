from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import LoginAttempt

def get_client_ip(request):
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@receiver(user_logged_in)
def log_successful_login(sender, request, user, **kwargs):
    if request:
        ip = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        LoginAttempt.objects.create(
            user=user,
            username=user.username,
            ip_address=ip,
            user_agent=user_agent,
            status='success'
        )

@receiver(user_login_failed)
def log_failed_login(sender, credentials, request=None, **kwargs):
    username = credentials.get('username', '')
    ip = get_client_ip(request) if request else None
    user_agent = request.META.get('HTTP_USER_AGENT', '') if request else ''
    
    User = get_user_model()
    try:
        user = User.objects.filter(username=username).first()
    except Exception:
        user = None

    LoginAttempt.objects.create(
        user=user,
        username=username,
        ip_address=ip,
        user_agent=user_agent,
        status='failed'
    )
