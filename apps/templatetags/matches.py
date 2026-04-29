from django import template

register = template.Library()

@register.filter(name='is_list')
def is_list(value):
    """
    Sprawdza, czy podana wartość jest listą.
    """
    return isinstance(value, list)

@register.filter(name='bar_class')
def bar_class(value):
    """
    Zwraca klasę CSS dla paska postępu na podstawie wartości procentowej.
    """
    try:
        value = int(value)
        if value >= 70:
            return 'progress-bar-success'
        if value >= 40:
            return 'progress-bar-warning'
        return 'progress-bar-danger'
    except (ValueError, TypeError):
        return 'progress-bar-danger'

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Umożliwia dostęp do klucza słownika przy użyciu zmiennej w szablonie Django.
    """
    if hasattr(dictionary, 'get'):
        return dictionary.get(key)
    return None

@register.filter(name='get_stat_icon')
def get_stat_icon(label):
    """
    Zwraca klasę ikony Font Awesome na podstawie etykiety statystyki.
    """
    icon_map = {
        # Serwis
        'Asy serwisowe': 'fa-solid fa-bolt',
        'Podwójne błędy': 'fa-solid fa-circle-exclamation',
        'Skuteczność 1 serwisu': 'fa-solid fa-percent',
        'Wygrane po 1 serwisie': 'fa-solid fa-trophy',
        'Skuteczność 2 serwisu': 'fa-solid fa-percent',
        'Wygrane po 2 serwisie': 'fa-solid fa-trophy',
        'Punkty serwisowe': 'fa-solid fa-server',
        'Gemy serwisowe': 'fa-solid fa-gamepad',
        'Break pointy bronione': 'fa-solid fa-shield-halved',
        # Return
        'Punkty returnowe': 'fa-solid fa-reply-all',
        'Break pointy wykorzystane': 'fa-solid fa-hand-fist',
        # Ogólne
        'Winner-y': 'fa-solid fa-star',
        'Niewymuszone błędy': 'fa-solid fa-magnifying-glass-minus',
        'Punkty zdobyte': 'fa-solid fa-plus-minus',
        'Maksymalna prędkość serwisu': 'fa-solid fa-gauge-high',
        'Średnia prędkość 1 serwisu': 'fa-solid fa-gauge',
        'Średnia prędkość 2 serwisu': 'fa-solid fa-gauge-simple',
    }
    return icon_map.get(label, 'fa-solid fa-chart-simple') # Domyślna ikona

@register.filter(name='compare_stats')
def compare_stats(p1_val, args):
    """
    Porównuje statystyki dwóch graczy i zwraca 'p1' lub 'p2' dla zwycięzcy.
    Uwzględnia, czy wyższa wartość jest lepsza, czy gorsza.
    Użycie: {{ p1_val|compare_stats:"label,p2_val" }}
    """
    # Statystyki, dla których niższa wartość jest lepsza
    lower_is_better = ['Podwójne błędy', 'Niewymuszone błędy']

    # Bezpieczne rozdzielanie argumentów
    args_parts = str(args).split(',', 1)
    if len(args_parts) != 2:
        return None # Nie można porównać, jeśli brakuje danych
    label, p2_val = args_parts

    try:
        # Usuń '%' i przekonwertuj na float, jeśli to możliwe
        val1 = float(str(p1_val).strip().replace('%', ''))
        val2 = float(str(p2_val).strip().replace('%', ''))

        if label in lower_is_better:
            if val1 < val2:
                return 'p1'
            if val2 < val1:
                return 'p2'
        else:
            if val1 > val2:
                return 'p1'
            if val2 > val1:
                return 'p2'
    except (ValueError, TypeError):
        # Nie można porównać wartości (np. są to stringi '-')
        return None
    return None # Wartości są równe