from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
import logging
from django.conf import settings
import json

from .models import Notifications

logger = logging.getLogger(__name__)

def add_notification(request, message, level_tag='info'):
    """
    Saves a Django message as a Notification object.
    """
    if request.user.is_authenticated:
        Notifications.objects.create(
            user=request.user,
            message=message,
        )
        messages.add_message(request, getattr(messages, level_tag.upper(), messages.INFO), message)


def notify_user(user, message, level_tag='info'):
    """
    Saves a message as a Notification object for a specific user.
    """
    if user.is_authenticated:
        Notifications.objects.create(
            user=user,
            message=message,
        )
        

@csrf_exempt
def get_vapid_public_key(request):
    """API endpoint to retrieve VAPID public key."""
    if request.method == 'GET':
        public_key = getattr(settings, 'VAPID_PUBLIC_KEY', '')
        logger.info("VAPID public key retrieved via API.")
        return JsonResponse({'public_key': public_key})
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def save_subscription(request):
    """API endpoint to save a push subscription."""
    if request.method == 'POST':
        data = json.loads(request.body)
        subscription = data.get('subscription', {})
        user_id = data.get('user_id')
        cache_key = f'push_subscription_{user_id}'
        cache.set(cache_key, subscription, 86400 * 30)
        logger.info(f"Push subscription saved for user {user_id}.")
        return JsonResponse({'status': 'success'})
    return JsonResponse({'error': 'Method not allowed'}, status=405)

# Usunięto funkcje send_push_notification_to_all i send_push_notification

@login_required
def get_notifications(request):
    """
    Returns a list of notifications for the logged-in user.
    """
    notifications = Notifications.objects.filter(user=request.user, is_read=False).order_by('-created_at')
    data = [{
        'id': n.id,
        'message': n.message,
        'created_at': n.created_at.strftime('%Y-%m-%d %H:%M'),
        'is_read': n.is_read
    } for n in notifications]
    return JsonResponse({'notifications': data, 'count': notifications.count()})

@login_required
@csrf_exempt
def read_all_notifications(request):
    """
    Marks all notifications for the logged-in user as read.
    """
    if request.method == 'POST':
        Notifications.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'failed', 'error': 'Invalid request method'}, status=405)

@login_required
def get_unread_count(request):
    """
    Returns the count of unread notifications for the logged-in user.
    """
    count = Notifications.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'count': count})

# Usunięto funkcje send_new_user_notification i get_new_registrations