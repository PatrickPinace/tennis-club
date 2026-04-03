import sys
from fitparse import FitFile

# Lista pól, które mają zostać pobrane - ich nazwy są zapisane w pliku FIT.
REQUESTED_FIELDS = [
    "Score", "Aces", "Double Faults", "First serve %",
    "Win % on first serve", "Win % on second serve", "Points",
    "Serving points", "Receiving points", "Games", "Breakpoints",
    "Set Points", "Match Points", "Sets durations", "Winners",
    "Unforced errors"
]


def extract_tennis_stats(fit_file_path):
    """
    Parsuje plik FIT, używając najbardziej podstawowej metody, polegającej na
    odczycie nazwy pola i jego wartości w wiadomości 'session'.
    """

    if not fit_file_path:
        print("Błąd: Proszę podać ścieżkę do pliku FIT.")
        return

    try:
        # Krok 1: Inicjalizacja FitFile bez wywoływania read()
        fitfile = FitFile(fit_file_path)
    except Exception as e:
        print(f"\nBŁĄD: Wystąpił błąd podczas otwierania pliku FIT: {e}")
        return

    print(f"\n--- 🎾 Parsowanie pliku: {fit_file_path} ---")
    tennis_stats = {}
    found_session = False
    found_dev_data = False

    # Krok 2: Iteracja po wiadomościach
    for record in fitfile.get_messages():

        # Interesuje nas tylko wiadomość podsumowująca 'session'
        if hasattr(record, 'name') and record.name == 'session':
            found_session = True

            # Krok 3: Iteracja po polach w wiadomości
            for field in record.fields:

                # Sprawdzamy, czy nazwa pola jest w naszej liście (bez sprawdzania 'is_developer_field')
                if field.name in REQUESTED_FIELDS:
                    found_dev_data = True
                    value = field.value

                    if value is not None:
                        tennis_stats[field.name] = value

            break  # Przerywamy po znalezieniu i przetworzeniu wiadomości 'session'

    if not found_session:
        print("Nie znaleziono wiadomości 'session' w pliku. Upewnij się, że plik jest aktywnością z zegarka.")
        return

    if not found_dev_data:
        print(
            "Nie znaleziono niestandardowych pól deweloperskich. Upewnij się, że plik pochodzi z aplikacji Tennis Studio.")
        return

    # --- Wypisanie wyników ---
    print("\n✅ Pomyślnie znalezione statystyki Tennis Studio:")

    for field_name in REQUESTED_FIELDS:
        value = tennis_stats.get(field_name, "N/A (brak danych lub błąd mapowania)")
        # Przygotowanie do wyświetlenia
        display_value = ' '.join(map(str, value)) if isinstance(value, list) else value

        print(f"- {field_name:25}: {display_value}")

    print("\n--- Koniec parsowania ---")


# Uruchomienie skryptu z argumentem z linii komend
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Użycie: python parse_fit_file.py <ścieżka_do_pliku_fit>")
        sys.exit(1)

    file_path = sys.argv[1]
    extract_tennis_stats(file_path)