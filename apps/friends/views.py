from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.template import loader
from django.shortcuts import redirect
from .models import Friend
from .models import Friend, FriendRequest # Import FriendRequest
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta

import logging
from django.db import transaction # Import transaction
logger = logging.getLogger(__name__)


@login_required()
def friends_list(request):
    if request.method == 'POST':
        from .forms import FriendAddForm, FriendRemoveForm # Import forms here to avoid circular dependency if models import views
        action = request.POST.get('action')
        if action == 'send_friend_request': # Changed action name
            add_form = FriendAddForm(request.POST, user_queryset=User.objects.filter(is_active=True, is_superuser=False).exclude(id=request.user.id))
            if add_form.is_valid():
                receiver = add_form.cleaned_data['friend_id'] # Renamed 'friend' to 'receiver' for clarity
                if receiver == request.user:
                    messages.error(request, "Nie możesz wysłać zaproszenia do samego siebie.")
                else:
                    try:
                        # Check if already friends (mutual friendship)
                        if Friend.objects.filter(user=request.user, friend=receiver).exists() and \
                           Friend.objects.filter(user=receiver, friend=request.user).exists():
                            messages.error(request, f"Jesteś już znajomym z {receiver.username}.")
                        # Check if a request is already pending from sender to receiver
                        elif FriendRequest.objects.filter(sender=request.user, receiver=receiver, status='pending').exists():
                            messages.info(request, f"Wysłano już zaproszenie do {receiver.username}.")
                        # Check if a request is already pending from receiver to sender (incoming request)
                        elif FriendRequest.objects.filter(sender=receiver, receiver=request.user, status='pending').exists():
                            messages.info(request, f"{receiver.username} już wysłał Ci zaproszenie. Możesz je zaakceptować.")
                        else:
                            # Znajdź lub utwórz zaproszenie. Jeśli istnieje (np. odrzucone), zaktualizuj je.
                            # Jeśli nie istnieje, utwórz nowe.
                            friend_request, created = FriendRequest.objects.get_or_create(
                                sender=request.user, receiver=receiver
                            )
                            friend_request.status = 'pending'
                            friend_request.save()
                            messages.success(request, f"Wysłano zaproszenie do znajomych do {receiver.username}.")
                            return redirect('friends_list')
                    except IntegrityError:
                        messages.error(request, "Wystąpił błąd podczas wysyłania zaproszenia (możliwe, że zaproszenie już istnieje).")
                    except Exception as e:
                        logger.error(f"Error sending friend request: {e}")
                        messages.error(request, "Wystąpił nieoczekiwany błąd podczas wysyłania zaproszenia.")
            else:
                messages.error(request, "Niepoprawny formularz wysyłania zaproszenia.")
        
        elif action == 'accept_friend_request':
            request_id = request.POST.get('request_id')
            try:
                friend_request = FriendRequest.objects.get(pk=request_id, receiver=request.user, status='pending')
                with transaction.atomic():
                    # Create mutual friendships
                    Friend.objects.create(user=friend_request.sender, friend=friend_request.receiver)
                    Friend.objects.create(user=friend_request.receiver, friend=friend_request.sender)
                    friend_request.status = 'accepted'
                    friend_request.save()

                messages.success(request, f"Zaakceptowano zaproszenie od {friend_request.sender.username}.")
                return redirect('friends_list')
            except FriendRequest.DoesNotExist:
                messages.error(request, "Zaproszenie nie istnieje lub nie masz uprawnień do jego zaakceptowania.")
            except IntegrityError:
                messages.error(request, "Wystąpił błąd podczas akceptowania zaproszenia (możliwe, że jesteście już znajomymi).")
            except Exception as e:
                logger.error(f"Error accepting friend request: {e}")
                messages.error(request, "Wystąpił nieoczekiwany błąd podczas akceptowania zaproszenia.")

        elif action == 'reject_friend_request':
            request_id = request.POST.get('request_id')
            try:
                friend_request = FriendRequest.objects.get(pk=request_id, receiver=request.user, status='pending')
                friend_request.status = 'rejected'
                friend_request.save()

                messages.info(request, f"Odrzucono zaproszenie od {friend_request.sender.username}.")
                return redirect('friends_list')
            except FriendRequest.DoesNotExist:
                messages.error(request, "Zaproszenie nie istnieje lub nie masz uprawnień do jego odrzucenia.")
            except Exception as e:
                logger.error(f"Error rejecting friend request: {e}")
                messages.error(request, "Wystąpił nieoczekiwany błąd podczas odrzucania zaproszenia.")

        elif action == 'cancel_friend_request':
            request_id = request.POST.get('request_id')
            try:
                # Upewnij się, że tylko nadawca może anulować swoje zaproszenie
                friend_request = FriendRequest.objects.get(pk=request_id, sender=request.user, status='pending')
                friend_request.delete()
                messages.success(request, f"Anulowano zaproszenie do znajomych dla {friend_request.receiver.username}.")
                return redirect('friends_list')
            except FriendRequest.DoesNotExist: 
                messages.error(request, "Zaproszenie nie istnieje lub nie masz uprawnień do jego anulowania.")
            except Exception as e:
                logger.error(f"Error cancelling friend request: {e}")
                messages.error(request, "Wystąpił nieoczekiwany błąd podczas anulowania zaproszenia.")

        elif action == 'remove_friend':
            remove_form = FriendRemoveForm(request.POST)
            if remove_form.is_valid():
                friend_id_to_remove = remove_form.cleaned_data['friend_id']
                try:
                    with transaction.atomic():
                        # Remove mutual friendships
                        Friend.objects.filter(user=request.user, friend_id=friend_id_to_remove).delete()
                        Friend.objects.filter(user_id=friend_id_to_remove, friend=request.user).delete()
                    messages.success(request, "Usunięto znajomego.")
                    return redirect('friends_list')
                except Exception as e:
                    logger.error(f"Error removing friend: {e}")
                    messages.error(request, "Wystąpił błąd podczas usuwania znajomego.")
            else:
                messages.error(request, "Niepoprawny formularz usuwania znajomego.")
    
    # --- Data fetching for context ---
    context = {}

    # Get IDs of all users who are friends with the current user (mutual friendship)
    friend_ids = Friend.objects.filter(user=request.user).values_list('friend_id', flat=True)
    
    # Get list of friends with additional info
    friends = Friend.objects.filter(user=request.user).select_related('friend').order_by('friend__first_name', 'friend__last_name')

    # Dodaj informacje o ostatniej aktywności i statusie online
    five_minutes_ago = timezone.now() - timedelta(minutes=5)
    for f in friends:
        last_seen = cache.get(f'seen_{f.friend.username}')
        # Użyj last_seen jeśli jest dostępne, w przeciwnym razie wróć do last_login
        f.friend.last_activity = last_seen if last_seen else f.friend.last_login
        # Sprawdź, czy użytkownik był widziany i czy czas aktywności jest nowszy niż 5 minut temu
        if last_seen and last_seen > five_minutes_ago:
            f.friend.is_online = True

    # Get incoming friend requests for the current user
    incoming_requests = FriendRequest.objects.filter(receiver=request.user, status='pending').select_related('sender').order_by('-timestamp')

    # Get outgoing friend requests sent by the current user
    outgoing_requests = FriendRequest.objects.filter(sender=request.user, status='pending').select_related('receiver').order_by('-timestamp')

    # Get IDs of users involved in any pending requests (either sent or received by current user)
    pending_request_users_ids = set(
        FriendRequest.objects.filter(receiver=request.user, status='pending').values_list('sender_id', flat=True)
    )
    pending_request_users_ids.update(
        FriendRequest.objects.filter(sender=request.user, status='pending').values_list('receiver_id', flat=True)
    )

    # Get all users, excluding current user, already friends, and users with pending requests
    users = User.objects.filter(is_active=True, is_superuser=False) \
                        .exclude(id=request.user.id) \
                        .exclude(id__in=friend_ids) \
                        .exclude(id__in=pending_request_users_ids) \
                        .order_by('first_name', 'last_name')

    # Last 3 registered users (IDs) to highlight, excluding current user, friends, and users with pending requests
    recent_user_ids = list(
        User.objects.filter(is_active=True, is_superuser=False)
        .order_by('-date_joined')
        .exclude(id=request.user.id) # Exclude current user from recent suggestions
        .exclude(id__in=friend_ids) # Exclude already friends
        .exclude(id__in=pending_request_users_ids) # Exclude users with pending requests
        .values_list('id', flat=True)[:3]
    )

    context['friends'] = friends
    context['users'] = users
    context['recent_user_ids'] = recent_user_ids
    context['incoming_requests'] = incoming_requests
    context['outgoing_requests'] = outgoing_requests
    html_template = loader.get_template('friends/friends_list.html')
    return HttpResponse(html_template.render(context, request))