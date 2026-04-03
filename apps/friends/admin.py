from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Q
from .models import Friend, FriendRequest

# ==========================================
# 0. Filtry niestandardowe
# ==========================================
class SymmetricFriendFilter(admin.SimpleListFilter):
    title = 'Symetria znajomości'
    parameter_name = 'symmetric'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Tak (Obustronna)'),
            ('no', 'Nie (Jednostronna)'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            ids = [f.id for f in queryset if Friend.objects.filter(user=f.friend, friend=f.user).exists()]
            return queryset.filter(id__in=ids)
        
        if self.value() == 'no':
            ids = [f.id for f in queryset if not Friend.objects.filter(user=f.friend, friend=f.user).exists()]
            return queryset.filter(id__in=ids)
        
        return queryset

# ==========================================
# 1. Panel dla modelu Friend (Znajomości)
# ==========================================
@admin.register(Friend)
class FriendAdmin(admin.ModelAdmin):
    list_display = ('user', 'friend', 'is_symmetric', 'id')
    search_fields = ('user__username', 'user__email', 'friend__username', 'friend__email')
    raw_id_fields = ('user', 'friend')
    list_filter = (SymmetricFriendFilter,)
    list_select_related = ('user', 'friend') # Optymalizacja zapytań

    def is_symmetric(self, obj):
        # Sprawdź czy istnieje relacja odwrotna
        symmetric = Friend.objects.filter(user=obj.friend, friend=obj.user).exists()
        color = 'green' if symmetric else 'red'
        icon = '✔' if symmetric else '✘'
        return format_html('<span style="color: {};">{} {}</span>', color, icon, "Tak" if symmetric else "Nie")
    is_symmetric.short_description = "Symetryczna?"

# ==========================================
# 2. Panel dla modelu FriendRequest (Zaproszenia)
# ==========================================
@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'status_colored', 'timestamp')
    list_filter = ('status', 'timestamp')
    search_fields = ('sender__username', 'sender__email', 'receiver__username', 'receiver__email')
    raw_id_fields = ('sender', 'receiver')
    actions = ['accept_requests', 'reject_requests']
    list_select_related = ('sender', 'receiver') # Optymalizacja

    def status_colored(self, obj):
        colors = {
            'pending': 'orange',
            'accepted': 'green',
            'rejected': 'red',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.status.upper()
        )
    status_colored.short_description = 'Status'

    def accept_requests(self, request, queryset):
        count = 0
        for req in queryset:
            if req.status != 'accepted':
                req.status = 'accepted'
                req.save()
                # Tworzenie relacji Friend - OBUSTRONNIE dla spójności
                Friend.objects.get_or_create(user=req.sender, friend=req.receiver)
                Friend.objects.get_or_create(user=req.receiver, friend=req.sender)
                count += 1
        self.message_user(request, f"Zaakceptowano {count} zaproszeń i utworzono obustronne znajomości.")
    accept_requests.short_description = "Zaakceptuj wybrane zaproszenia (tworzy relację obustronną)"

    def reject_requests(self, request, queryset):
        rows_updated = queryset.update(status='rejected')
        self.message_user(request, f"Odrzucono {rows_updated} zaproszeń.")
    reject_requests.short_description = "Odrzuć wybrane zaproszenia"