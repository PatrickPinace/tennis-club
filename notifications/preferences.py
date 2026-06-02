# notifications/preferences.py
#
# Definicja grup preferencji powiadomień v1.
# Każda grupa mapuje kilka event_type-ów na jedną opcję on/off dla użytkownika.
# Preferencja przechowywana jest per canonical event_type (pierwszy w liście).

PREFERENCE_GROUPS = [
    {
        'key': 'reservations',
        'label': 'Rezerwacje kortów',
        'description': 'Potwierdzenia, odrzucenia i anulowania rezerwacji kortów.',
        'event_types': [
            'court.reservation.created',
            'court.reservation.accepted',
            'court.reservation.rejected',
            'court.reservation.cancelled',
        ],
    },
    {
        'key': 'tournament_status',
        'label': 'Statusy turniejów',
        'description': 'Informacje o starcie, zakończeniu lub anulowaniu turnieju.',
        'event_types': [
            'tournament.started',
            'tournament.finished',
            'tournament.cancelled',
        ],
    },
    {
        'key': 'tournament_participation',
        'label': 'Uczestnictwo w turnieju',
        'description': 'Dodanie, dołączenie lub wycofanie z turnieju.',
        'event_types': [
            'tournament.participant.added',
            'tournament.participant.joined',
            'tournament.participant.removed',
        ],
    },
    {
        'key': 'tournament_results',
        'label': 'Wyniki meczów',
        'description': 'Wpisane wyniki i walkovery w turniejach.',
        'event_types': [
            'tournament.match.score_entered',
            'tournament.match.walkover',
        ],
    },
    {
        'key': 'ladder',
        'label': 'Wyzwania w drabince',
        'description': 'Wysłane, zaakceptowane i odrzucone wyzwania w turnieju Ladder.',
        'event_types': [
            'tournament.ladder.challenge_sent',
            'tournament.ladder.challenge_accepted',
            'tournament.ladder.challenge_rejected',
        ],
    },
]

# Mapa: event_type → canonical event_type grupy (szybkie lookup w helperze)
_EVENT_TO_CANONICAL: dict[str, str] = {}
for _group in PREFERENCE_GROUPS:
    _canonical = _group['event_types'][0]
    for _et in _group['event_types']:
        _EVENT_TO_CANONICAL[_et] = _canonical


def group_key_for_event(event_type: str) -> str | None:
    """Zwraca canonical event_type grupy dla danego event_type, lub None jeśli nie w żadnej grupie."""
    return _EVENT_TO_CANONICAL.get(event_type)
