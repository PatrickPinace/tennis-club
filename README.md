# TennisClub

Rozbudowana aplikacja internetowa do zarządzania klubem tenisowym, rezerwacjami kortów, organizacją turniejów i rankingów tenisowych.

## Funkcjonalności

*   **Rezerwacja Kortów:** System grafików i rezerwacji online.
*   **Turnieje:** Zarządzanie turniejami, drabinki turniejowe, harmonogramy.
*   **Rankingi:** Precomputed ranking graczy z automatycznym przeliczaniem po zakończeniu turnieju (snapshot w tabeli `PlayerRanking`, rebuild przez `python manage.py rebuild_rankings`).
*   **Społeczność:** Profile graczy, wyszukiwanie sparingpartnerów, lista znajomych.
*   **Czat:** Wbudowany komunikator dla użytkowników.
*   **Powiadomienia:** Notyfikacje wewnątrz aplikacji oraz powiadomienia Push.

## Technologie

*   **Backend:** Django 5, Python 3.12+
*   **Baza danych:** PostgreSQL (produkcja na OVH), SQLite (dev)
*   **Frontend:** Django Templates, HTML5, CSS3 (custom design system), vanilla JavaScript

## Instalacja i Uruchomienie

### Wymagania

*   Python 3.12+
*   PostgreSQL (lub SQLite dla developmentu)

### Konfiguracja Środowiska

1.  **Sklonuj repozytorium:**
    ```bash
    git clone https://github.com/Skorpi86/tennis-club.git
    cd tennis-club
    ```

2.  **Utwórz i aktywuj wirtualne środowisko:**
    ```bash
    python -m venv .venv
    # Windows:
    .venv\Scripts\activate
    # Linux/Mac:
    source .venv/bin/activate
    ```

3.  **Zainstaluj zależności:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Skonfiguruj zmienne środowiskowe:**
    Utwórz plik `.env` w głównym katalogu na podstawie poniższego schematu:
    ```ini
    SECRET_KEY=twoj_sekretny_klucz
    DEBUG=True
    DB_PASS=twoje_haslo_do_bazy
    FIELD_ENCRYPTION_KEY=klucz_szyfrowania_pol
    DJANGO_ENV=development
    VAPID_PUBLIC_KEY=...
    VAPID_PRIVATE_KEY=...
    ```

5.  **Przygotuj bazę danych:**
    ```bash
    python manage.py migrate
    python manage.py createsuperuser
    ```

6.  **Przelicz ranking** (po imporcie danych lub pierwszym uruchomieniu):
    ```bash
    python manage.py rebuild_rankings
    ```

### Uruchomienie

```bash
python manage.py runserver
```

## Powiadomienia Push na Telefonie

Aplikacja obsługuje powiadomienia push na telefonie poprzez Service Worker i Web Push API.

### Konfiguracja VAPID Keys

Klucze VAPID są wymagane do działania powiadomień. Należy je wygenerować i dodać do pliku `.env`.

1.  **Generowanie kluczy:**
    ```bash
    python -c "from py_vapid import Vapid; v = Vapid(); v.generate_keys(); print('Public:', v.public_key); print('Private:', v.private_key)"
    ```

2.  **Dodaj do `.env`:**
    ```ini
    VAPID_PUBLIC_KEY=wygenerowany_klucz_publiczny
    VAPID_PRIVATE_KEY=wygenerowany_klucz_prywatny
    ```

3.  **Ustawienia w `core/settings.py`:**
    Upewnij się, że settings.py wczytuje te zmienne z pliku `.env`.

### Instalacja na Telefonie (PWA)

1.  Otwórz aplikację w przeglądarce na telefonie.
2.  Zaloguj się.
3.  Zaakceptuj prośbę o powiadomienia ("Zezwól").
4.  Możesz dodać aplikację do ekranu głównego ("Zainstaluj aplikację" lub "Dodaj do ekranu głównego").

## Aktualizacja

Projekt posiada skrypt `update.sh` do automatyzacji aktualizacji na serwerze produkcyjnym (Linux).

```bash
./update.sh --safe  # Domyślny tryb
./update.sh --hard  # Reset zmian lokalnych
```
