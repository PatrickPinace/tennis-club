# Tennis Club v2 - PostgreSQL Migration

## Przegląd

Tennis Club v2 to przepisana wersja aplikacji do zarządzania klubem tenisowym, z:
- **PostgreSQL** zamiast MySQL jako baza danych
- **Uproszczonymi modelami** - tylko core functionality (MVP)
- **psycopg 3.x** jako adapter PostgreSQL (zgodnie z rekomendacją Django)
- **Czystą strukturą** bez bagażu testowej bazy danych

## Wymagania

- Python 3.12+
- PostgreSQL 14+
- pip
- virtualenv (opcjonalnie)

## Instalacja

### 1. Przygotowanie środowiska

```bash
# Sklonuj repozytorium i przełącz się na branch v2-postgres
git checkout v2-postgres

# Utwórz wirtualne środowisko
python -m venv .venv

# Aktywuj środowisko
source .venv/bin/activate  # Linux/Mac
# lub
.venv\Scripts\activate  # Windows
```

### 2. Instalacja zależności

```bash
pip install -r requirements_v2.txt
```

### 3. Konfiguracja PostgreSQL

#### Na lokalnym środowisku (development):

```bash
# Zainstaluj PostgreSQL jeśli nie masz:
# Ubuntu/Debian:
sudo apt install postgresql postgresql-contrib

# macOS (Homebrew):
brew install postgresql@14
brew services start postgresql@14

# Utwórz bazę danych:
sudo -u postgres psql
CREATE DATABASE tennis_club;
CREATE USER tennis_admin WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE tennis_club TO tennis_admin;
ALTER DATABASE tennis_club OWNER TO tennis_admin;
\q
```

#### Na OVH (production):

*Konfiguracja zostanie wykonana wspólnie podczas wdrożenia.*

### 4. Plik `.env`

Utwórz plik `.env` w głównym katalogu projektu:

```ini
# Environment
DJANGO_ENV=development  # lub 'production' na OVH

# Secret Keys
SECRET_KEY=your-secret-key-here-change-in-production

# Database (PostgreSQL)
DB_NAME=tennis_club
DB_USER=tennis_admin
DB_PASS=your_password
DB_HOST=localhost  # lub IP serwera OVH
DB_PORT=5432
```

**Generowanie SECRET_KEY:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 5. Migracje bazy danych

```bash
# Użyj settings_v2.py
export DJANGO_SETTINGS_MODULE=core.settings_v2

# Lub dodaj do .env:
# DJANGO_SETTINGS_MODULE=core.settings_v2

# Wykonaj migracje
python manage.py makemigrations
python manage.py migrate

# Utwórz superusera
python manage.py createsuperuser
```

### 6. Uruchomienie serwera

```bash
# Development
python manage.py runserver

# Otwórz w przeglądarce:
# http://127.0.0.1:8000/admin/
```

## Struktura projektu v2

```
tennis-club/
├── v2_core/                    # Główny app z modelami v2
│   ├── models/
│   │   ├── __init__.py
│   │   ├── users.py           # Profile
│   │   ├── facilities.py      # Facility, Court, Reservation
│   │   ├── matches.py         # Match
│   │   ├── tournaments.py     # Tournament, Participant, etc.
│   │   ├── rankings.py        # RankingHistory, TournamentRankPoints
│   │   ├── notifications.py   # Notification
│   │   └── friends.py         # Friendship, FriendRequest
│   ├── admin.py               # Django Admin config
│   ├── apps.py
│   └── views.py
├── core/
│   ├── settings.py            # Stare ustawienia (MySQL)
│   ├── settings_v2.py         # NOWE ustawienia (PostgreSQL)
│   ├── urls.py
│   └── wsgi.py
├── workdir/
│   └── MODELS_V2_DESIGN.md    # Dokumentacja designu
├── requirements.txt           # Stare (MySQL)
├── requirements_v2.txt        # NOWE (PostgreSQL + psycopg)
└── README_V2.md               # Ten plik
```

## Zakres MVP (v1 Core)

### ✅ Zaimplementowane:

1. **Users & Profiles** - profil użytkownika + ranking (Elo, punkty)
2. **Facilities & Courts** - obiekty tenisowe i korty
3. **Reservations** - rezerwacje kortów
4. **Matches** - mecze (singiel/debeł)
5. **Tournaments** - turnieje:
   - Round Robin (liga - każdy z każdym)
   - Single Elimination (puchar)
6. **Rankings** - historia rankingu
7. **Notifications** - powiadomienia
8. **Friends** - znajomości

### 🔴 Odłożone na v2:

- Chat (prywatny + meczowy)
- Garmin Connect integration
- Egzotyczne formaty turniejów (Ladder, Americano, Swiss, Double Elimination)
- Activities & TennisData (szczegółowe statystyki)

## Konfiguracja NocoDB

### 1. Instalacja NocoDB (Docker)

```bash
# Na serwerze OVH:
docker run -d --name nocodb \
  -p 8080:8080 \
  nocodb/nocodb:latest
```

### 2. Podłączenie do PostgreSQL

1. Otwórz NocoDB: `http://your-ovh-ip:8080`
2. Utwórz nowe workspace
3. **Add new data source** → External Database
4. Wybierz **PostgreSQL**
5. Wypełnij dane:
   ```
   Host: localhost (lub IP)
   Port: 5432
   Database: tennis_club
   Username: tennis_admin
   Password: [twoje hasło]
   ```
6. **Test connection** → **Connect**

### 3. Uprawnienia w NocoDB

**Read-Only Tables (tylko podgląd):**
- `ranking_history` - generowane przez Django
- `tournament_matches` - wyniki zarządzane przez system
- `notifications` - tylko Django tworzy

**Editable Tables (admin może edytować):**
- `reservations` - zmiana statusów rezerwacji
- `tournaments` - zarządzanie turniejami
- `tournament_participants` - dodawanie/usuwanie uczestników
- `facilities` / `courts` - zarządzanie obiektami

**Hidden Tables:**
- `auth_*` - Django auth (tylko przez Django Admin)

## Deployment na OVH

### Przygotowanie do produkcji:

```bash
# Zbierz pliki statyczne
python manage.py collectstatic --noinput

# Sprawdź konfigurację
python manage.py check --deploy
```

### Uruchomienie z Gunicorn (WSGI):

```bash
# Zainstaluj Gunicorn
pip install gunicorn

# Uruchom
gunicorn core.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --access-logfile - \
  --error-logfile - \
  --env DJANGO_SETTINGS_MODULE=core.settings_v2
```

### Systemd service (OVH):

*Zostanie skonfigurowane wspólnie podczas wdrożenia.*

## Migracja danych ze starej bazy

**NIE ROBIMY MIGRACJI DANYCH!**

Stara baza była testowa. Zaczynamy z czystą bazą PostgreSQL:
1. Nowe ID
2. Nowe dane produkcyjne
3. Brak dziedziczenia błędów struktury

### Workflow po deployment:

1. `python manage.py migrate` (czyste tabele)
2. `python manage.py createsuperuser`
3. Dodanie podstawowych danych przez Django Admin:
   - Facilities & Courts
   - TournamentRankPoints (rangi 1-3)
4. Podłączenie NocoDB
5. Testowanie

## Troubleshooting

### Problem: `ModuleNotFoundError: No module named 'psycopg'`

```bash
pip install "psycopg[binary]"
```

### Problem: PostgreSQL connection refused

```bash
# Sprawdź czy PostgreSQL działa:
sudo systemctl status postgresql

# Sprawdź konfigurację pg_hba.conf:
sudo nano /etc/postgresql/14/main/pg_hba.conf
# Dodaj linię:
# host    tennis_club    tennis_admin    127.0.0.1/32    md5

# Restart PostgreSQL:
sudo systemctl restart postgresql
```

### Problem: Permission denied for database

```bash
sudo -u postgres psql
GRANT ALL PRIVILEGES ON DATABASE tennis_club TO tennis_admin;
ALTER DATABASE tennis_club OWNER TO tennis_admin;
```

## Wsparcie

Dla problemów i pytań, skontaktuj się z zespołem deweloperskim.

---

**Branch:** `v2-postgres`
**Status:** In Development
**Last Updated:** 2026-03-23
