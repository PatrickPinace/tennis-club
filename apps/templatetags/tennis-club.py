from django import template

import logging
logger = logging.getLogger(__name__)

register = template.Library()

@register.filter
def replace_tags(tags):
    if tags == "error":
        return "danger"
    return tags
