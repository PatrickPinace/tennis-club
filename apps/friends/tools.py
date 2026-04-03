from django.contrib.auth.models import User
from .models import Friend, FriendRequest # Import FriendRequest
from django.db.models import Q


def convert_auth_user_id_to_name(request, user_id):
    try:
        user = User.objects.get(pk=user_id)
        return f"{user.first_name} {user.last_name}"
    except Exception:
        return "Konto Usunięte"


def get_friends_id(request):    
    # Assuming mutual Friend objects (A->B and B->A) are created
    # This will get IDs of users who are friends with request.user
    friend_ids = Friend.objects.filter(user=request.user).values_list('friend_id', flat=True)
    
    # Convert to set for unique IDs and add current user
    friend_ids_set = set(friend_ids)
    friend_ids_set.add(request.user.pk)
    return tuple(friend_ids_set)


def get_only_friends_id(request):
    # Assuming mutual Friend objects (A->B and B->A) are created
    # This will get IDs of users who are friends with request.user
    friend_ids = Friend.objects.filter(user=request.user).values_list('friend_id', flat=True)
    
    # Convert to set for unique IDs
    friend_ids_set = set(friend_ids)
    return tuple(friend_ids_set)