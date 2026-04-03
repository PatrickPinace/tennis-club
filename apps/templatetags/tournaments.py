from django import template

register = template.Library()


@register.filter(name='force_dot')
def force_dot(value):
    """Replaces comma with a dot in a number."""
    try:
        return str(value).replace(',', '.')
    except (ValueError, TypeError):
        return value


@register.filter(name='get_range')
def get_range(value):
    """Zwraca zakres licz do iteracji w pętli for"""
    try:
        return range(int(value))
    except (ValueError, TypeError):
        return range(0)


@register.filter(name='pow')
def pow_filter(base, exponent):
    """Podnosi `base` do potęgi `exponent`."""
    try:
        return base ** exponent
    except (ValueError, TypeError):
        return None


@register.filter(name='subtract')
def subtract_filter(value, arg):
    """Odejmuje `arg` od `value`."""
    try:
        return value - arg
    except (ValueError, TypeError):
        return None


@register.filter(name='multiply')
def multiply_filter(value, arg):
    """Mnoży `value` przez `arg`."""
    try:
        return value * arg
    except (ValueError, TypeError):
        return None


@register.filter(name='add')
def add_filter(value, arg):
    """Dodaje `arg` do `value`."""
    try:
        return value + arg
    except (ValueError, TypeError):
        return None


@register.filter(name='divide')
def divide_filter(value, arg):
    """Dzieli `value` przez `arg`."""
    try:
        if arg == 0:
            return None # Avoid division by zero
        return value / arg
    except (ValueError, TypeError):
        return None


@register.filter
def check_max_players(players, max_players):
    if not players:
        return players
    if len(players) < max_players:
        return players
    return "FULL"


@register.filter
def check_player(players, player_pk):
    if type(players) is not list:
        return "ERR"
    for row in players:
        if row == "FULL":
            return "FULL"
        elif row.get("player") == player_pk:
            return "JOINED"
    return "CAN_JOIN"


@register.filter
def get_name(dictionary, key):
    if dictionary.get(key):
        _value = dictionary.get(key)
        return _value["name"]
    return key


@register.filter
def get_tour(dictionary, tour_pk):
    return dictionary.get(tour_pk)


@register.filter
def get_counter(dictionary, name):
    return dictionary.get(name)


@register.filter
def humanize(key):
    """
    Convert a string to a human-readable format.
    """
    if key is None or not isinstance(key, str|int):
        return ""
    if key == 0:
        return "OTWARTY"
    elif key == 1:
        return "AKTYWNY"
    elif key == 2:
        return "ZAMKNIĘTY"
    else:
        return key


@register.filter(name='get_item')
def get_item(dictionary, key):
    """Pozwala na dostęp do elementu słownika lub pola formularza za pomocą zmiennej w szablonie."""
    if hasattr(dictionary, 'get'):
        return dictionary.get(key)
    elif hasattr(dictionary, '__getitem__'):
        try:
            return dictionary[key]
        except (KeyError, TypeError, IndexError):
            return None
    return None


@register.filter(name='where_status_in')
def where_status_in(queryset, statuses):
    """Filtruje queryset, zwracając tylko obiekty o statusie z podanej listy."""
    if not hasattr(queryset, 'filter'):
        return []
    
    status_list = [s.strip() for s in statuses.split(',')]
    return queryset.filter(status__in=status_list)


@register.filter
def filter_by_emoji(queryset, emoji):
    """Filtruje queryset reakcji po konkretnym emoji."""
    return queryset.filter(emoji=emoji)


@register.filter
def get_user_participant(standings, user):
    """Zwraca obiekt uczestnika dla danego użytkownika z listy standings."""
    if not user.is_authenticated:
        return None
    for standing in standings:
        if standing['participant'].user == user:
            return standing['participant']
    return None

@register.filter
def has_tennis_data(activities):
    """Sprawdza, czy jakakolwiek aktywność w queryset ma powiązane dane tenisowe."""
    return any(hasattr(activity, 'tennis_data') for activity in activities)


@register.filter
def short_name(user):
    """Zwraca imię i nazwisko w formacie 'I. Nazwisko'."""
    if not user:
        return ""
    first_name = user.first_name
    last_name = user.last_name
    if first_name and last_name:
        return f"{first_name[0]}. {last_name}"
    elif last_name:
        return last_name
    return user.username
