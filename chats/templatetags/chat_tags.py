from django import template
from ..models import ChatMessage

register = template.Library()

@register.simple_tag
def unread_chat_messages_count(user):
    """Zwraca liczbę nieprzeczytanych wiadomości dla danego użytkownika."""
    if not user.is_authenticated:
        return 0
    return ChatMessage.objects.filter(recipient=user, is_read=False).count()