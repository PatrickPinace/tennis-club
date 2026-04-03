from django.contrib import admin
from django.utils.html import format_html
from .models import ChatMessage, ChatImage, TournamentMatchChatMessage, TournamentMatchChatImage

class ChatImageInline(admin.TabularInline):
    """
    Umożliwia podgląd i dodawanie obrazków bezpośrednio
    w widoku edycji wiadomości.
    """
    model = ChatImage
    extra = 1  # Liczba pustych formularzy do dodania nowych obrazków
    readonly_fields = ('uploaded_at', 'image_preview')

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 100px; height: auto;" />', obj.image.url)
        return "-"
    image_preview.short_description = "Podgląd"

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    """
    Konfiguracja panelu administracyjnego dla modelu ChatMessage.
    """
    list_display = ('id', 'sender', 'recipient', 'short_content', 'timestamp', 'is_read')
    list_filter = ('is_read', 'timestamp')
    search_fields = ('sender__username', 'recipient__username', 'content')
    readonly_fields = ('sender', 'recipient', 'timestamp')
    inlines = [ChatImageInline]
    list_select_related = ('sender', 'recipient')

    def short_content(self, obj):
        if len(obj.content) > 50:
            return f"{obj.content[:50]}..."
        return obj.content
    short_content.short_description = "Treść"

@admin.register(ChatImage)
class ChatImageAdmin(admin.ModelAdmin):
    list_display = ('message', 'image_preview', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('message__id',)
    readonly_fields = ('message', 'image', 'uploaded_at')

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 50px; height: auto;" />', obj.image.url)
        return "-"
    image_preview.short_description = "Podgląd"

# --- Konfiguracja dla czatu meczowego ---

class TournamentMatchChatImageInline(admin.TabularInline):
    model = TournamentMatchChatImage
    extra = 1
    readonly_fields = ('uploaded_at', 'image_preview')

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 100px; height: auto;" />', obj.image.url)
        return "-"
    image_preview.short_description = "Podgląd"

@admin.register(TournamentMatchChatMessage)
class TournamentMatchChatMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_tournament_name', 'match', 'sender', 'short_content', 'timestamp')
    list_filter = ('timestamp', 'match__tournament')
    search_fields = ('sender__username', 'content', 'match__id', 'match__tournament__name')
    readonly_fields = ('sender', 'timestamp', 'match')
    inlines = [TournamentMatchChatImageInline]
    list_select_related = ('match', 'sender', 'match__tournament')

    def short_content(self, obj):
        if len(obj.content) > 50:
            return f"{obj.content[:50]}..."
        return obj.content
    short_content.short_description = "Treść"

    def get_tournament_name(self, obj):
        return obj.match.tournament.name
    get_tournament_name.short_description = "Turniej"
    get_tournament_name.admin_order_field = 'match__tournament__name'

@admin.register(TournamentMatchChatImage)
class TournamentMatchChatImageAdmin(admin.ModelAdmin):
    list_display = ('message', 'image_preview', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('message__id',)
    readonly_fields = ('message', 'image', 'uploaded_at')

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 50px; height: auto;" />', obj.image.url)
        return "-"
    image_preview.short_description = "Podgląd"
