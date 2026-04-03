from django.contrib import admin
from .models import Notifications

@admin.register(Notifications)
class NotificationsAdmin(admin.ModelAdmin):
    list_display = ('user', 'message_preview', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('user__username', 'message')
    list_select_related = ('user',)
    actions = ['mark_as_read', 'mark_as_unread']

    def message_preview(self, obj):
        return obj.message[:50] + "..." if len(obj.message) > 50 else obj.message
    message_preview.short_description = "Treść"

    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f"Oznaczono {updated} powiadomień jako przeczytane.")
    mark_as_read.short_description = "Oznacz wybrane jako przeczytane"

    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(request, f"Oznaczono {updated} powiadomień jako nieprzeczytane.")
    mark_as_unread.short_description = "Oznacz wybrane jako nieprzeczytane"
