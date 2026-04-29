from django import template

register = template.Library()

@register.filter(name='dict_lookup')
def dict_lookup(value, arg):
    """
    Umożliwia odnalezienie etykiety dla klucza w liście krotek (np. w choices modelu).
    Użycie: {{ klucz|dict_lookup:lista_wyborow }}
    """
    return dict(arg).get(value)