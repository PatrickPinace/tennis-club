from django import template

import logging
logger = logging.getLogger(__name__)

register = template.Library()

def is_friend(user, friends):
    for friend in friends:
        if str(friend["friend_id"]) == str(user['id']):
            return True
    return False

@register.filter
def skip_friends(users, friends):
    users_without_friends = []
    for user in users:
        if not is_friend(user, friends):
            users_without_friends.append(user)
    return users_without_friends


@register.filter
def add_break(value):
    """
    Replaces spaces with <br> tags for HTML rendering.
    """
    if isinstance(value, str):
        return value.replace(' ', '<br>')
    elif value is None:
        return '---'
    return value