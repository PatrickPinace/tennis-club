from apps.friends import tools as friends_tools

def convert_user_id_to_names(request, matches):
    for row in matches:
        for player in ["p1", "p2", "p3", "p4"]:
            original_id = row.get(player)
            if original_id is None:
                original_id = row.get(f"{player}_id")
            if row.get('match_offline') and player == "p1":
                row[f"{player}_id"] = 0
                row[player] = f"{request.user.first_name} {request.user.last_name}"
            elif row.get('match_offline') and player != "p1":
                row[f"{player}_id"] = original_id
                row[player] = friends_tools.convert_friend_id_to_name(request, original_id) if original_id else ""
            else:
                row[f"{player}_id"] = original_id
                row[player] = friends_tools.convert_auth_user_id_to_name(request, original_id) if original_id else ""


def get_users(request, online=True, **kwargs):    
    import locale
    locale.setlocale(locale.LC_COLLATE, "pl_PL.UTF-8")
    from django.contrib.auth.models import User
    from apps.friends.models import OnlineFriend, OfflineFriend
    users = []
    category = "ONLINE"
    if online:
        # join_auth_user previously: now pull User objects for friends
        friend_ids = OnlineFriend.objects.filter(user=request.user).values_list('friend_id', flat=True)
        response = list(User.objects.filter(id__in=friend_ids).values('id', 'first_name', 'last_name', 'email', 'last_login', 'date_joined', 'username'))
        # normalize to previous shape
        for r in response:
            r['friend_id'] = r.pop('id')
    else:
        category = "PRIV"
        response = list(OfflineFriend.objects.filter(user=request.user).values('id', 'first_name', 'last_name'))
    if not response:
        return []
    for row in response:
        if str(request.user) == row.get('username'):
            continue
        friend_id = row.get('friend_id') if online else row.get('id')
        user = {
            "id": friend_id,
            "name": f"{row.get('first_name')} {row.get('last_name')}",
            "category": category
        }
        users.append(user)
    if kwargs.get("sort") == "user_name":
        users.sort(key=lambda x: locale.strxfrm(x['name']))
    return users
