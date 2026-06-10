from django.contrib.auth.models import User

def convert_user_id_to_names(request, matches):
    player_ids = set()
    for row in matches:
        for player in ["p1", "p2", "p3", "p4"]:
            val = row.get(player) or row.get(f"{player}_id")
            if val:
                player_ids.add(val)
                
    users_dict = {u.id: f"{u.first_name} {u.last_name}" for u in User.objects.filter(id__in=player_ids)}
    
    for row in matches:
        for player in ["p1", "p2", "p3", "p4"]:
            original_id = row.get(player)
            if original_id is None:
                original_id = row.get(f"{player}_id")
            if row.get('match_offline') and player == "p1":
                row[f"{player}_id"] = 0
                row[player] = f"{request.user.first_name} {request.user.last_name}"
            else:
                row[f"{player}_id"] = original_id
                row[player] = users_dict.get(original_id, "Konto Usunięte") if original_id else ""

