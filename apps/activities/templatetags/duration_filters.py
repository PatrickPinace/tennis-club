from django import template

register = template.Library()

@register.filter
def format_duration(seconds):
    """Formats a duration from seconds into a human-readable string."""
    if not isinstance(seconds, (int, float)):
        return ""
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours} godz.")
    if minutes > 0:
        parts.append(f"{minutes} min.")
    
    return " ".join(parts) if parts else "0 min."

@register.filter
def divide(value, arg):
    """Divides the value by the argument."""
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return None