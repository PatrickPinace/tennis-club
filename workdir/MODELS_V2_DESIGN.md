# Tennis Club v2 - Design Dokumentacja

## Architektura

```
┌─────────────────────────────────────────┐
│         OVH VPS                         │
├─────────────────────────────────────────┤
│  PostgreSQL 14+ (port 5432)             │
│  └─ tennis_club (database)              │
│                                         │
│  Django 5.2+ (WSGI/Gunicorn)            │
│  ├─ psycopg 3.1.12+                     │
│  ├─ Business logic                      │
│  ├─ REST API (JWT auth)                 │
│  └─ Push notifications                  │
│                                         │
│  NocoDB (external data source)          │
│  └─ Spreadsheet UI nad PostgreSQL       │
└─────────────────────────────────────────┘
```

## Core v1 - Zakres MVP

### ✅ Included:
- **Users & Profiles** - użytkownicy + ranking (Elo + punkty)
- **Facilities & Courts** - obiekty tenisowe i korty
- **Reservations** - rezerwacje kortów
- **Matches** - mecze (singiel/debeł)
- **Tournaments** - turnieje (Round Robin + Single Elimination)
- **Rankings** - historia rankingu
- **Notifications** - powiadomienia
- **Friends** - znajomości (uproszczone)

### 🔴 Postponed to v2:
- Chat (prywatny + meczowy)
- Garmin integration
- Advanced tournament types (Ladder, Americano, Swiss)
- Activities & TennisData (detailed stats)

## Struktura bazy danych

### 1. Users & Profiles
```
profiles
├─ id (PK)
├─ user_id (FK → auth_user) UNIQUE
├─ birth_date
├─ city
├─ phone
├─ image
├─ elo_rating (INDEX)
├─ ranking_points (INDEX)
└─ created_at
```

### 2. Facilities & Courts
```
facilities
├─ id (PK)
├─ name
├─ address
├─ owner_id (FK → auth_user)
├─ description
├─ phone
├─ default_surface
├─ image
├─ is_active
└─ created_at

courts
├─ id (PK)
├─ facility_id (FK → facilities)
├─ number
├─ surface
├─ is_indoor
├─ is_active
└─ UNIQUE(facility_id, number)
```

### 3. Reservations
```
reservations
├─ id (PK)
├─ court_id (FK → courts) INDEX
├─ user_id (FK → auth_user) INDEX
├─ start_time INDEX
├─ end_time
├─ status INDEX
├─ notes
├─ created_at
└─ updated_at
```

### 4. Matches
```
matches
├─ id (PK)
├─ player1_id (FK → auth_user)
├─ player2_id (FK → auth_user)
├─ player3_id (FK → auth_user) NULL (debeł)
├─ player4_id (FK → auth_user) NULL (debeł)
├─ is_doubles
├─ set1_p1, set1_p2
├─ set2_p1, set2_p2
├─ set3_p1, set3_p2
├─ winner_side ('p1' | 'p2')
├─ match_date INDEX
├─ description
├─ court_id (FK → courts)
├─ created_at
└─ updated_at
```

### 5. Tournaments
```
tournaments
├─ id (PK)
├─ name
├─ description
├─ tournament_type ('round_robin' | 'single_elimination')
├─ match_format ('singles' | 'doubles')
├─ start_date INDEX
├─ end_date
├─ registration_deadline
├─ status INDEX
├─ facility_id (FK → facilities)
├─ rank (1-3)
├─ max_participants
├─ winner_id (FK → tournament_participants)
├─ created_by_id (FK → auth_user)
└─ created_at

tournament_configs (1:1 z tournaments)
├─ tournament_id (PK, FK → tournaments)
├─ sets_to_win
├─ games_per_set
├─ points_for_match_win (league)
├─ points_for_match_loss (league)
├─ points_for_set_win (league)
├─ use_seeding (elimination)
└─ third_place_match (elimination)

tournament_participants
├─ id (PK)
├─ tournament_id (FK → tournaments) INDEX
├─ user_id (FK → auth_user)
├─ partner_id (FK → auth_user) NULL (debeł)
├─ display_name
├─ seed
├─ status
├─ points (league stats)
├─ matches_won/lost
├─ sets_won/lost
├─ games_won/lost
├─ created_at
└─ UNIQUE(tournament_id, user_id)

tournament_matches
├─ id (PK)
├─ tournament_id (FK → tournaments) INDEX
├─ participant1_id (FK → tournament_participants)
├─ participant2_id (FK → tournament_participants)
├─ round_number
├─ match_number
├─ status INDEX
├─ scheduled_time INDEX
├─ set1_p1, set1_p2
├─ set2_p1, set2_p2
├─ set3_p1, set3_p2
├─ winner_id (FK → tournament_participants)
├─ court_id (FK → courts)
├─ created_at
├─ updated_at
└─ UNIQUE(tournament_id, round_number, match_number)
```

### 6. Rankings
```
ranking_history
├─ id (PK)
├─ user_id (FK → auth_user) INDEX
├─ date INDEX
├─ elo_rating
├─ ranking_points
├─ position
├─ total_matches
├─ wins
└─ losses

tournament_rank_points
├─ rank (PK, 1-3)
├─ winner_points
├─ finalist_points
├─ semifinal_points
├─ quarterfinal_points
└─ participation_points
```

### 7. Notifications
```
notifications
├─ id (PK)
├─ user_id (FK → auth_user) INDEX
├─ notification_type
├─ title
├─ message
├─ link
├─ is_read INDEX
└─ created_at INDEX
```

### 8. Friends
```
friendships
├─ id (PK)
├─ user_id (FK → auth_user)
├─ friend_id (FK → auth_user)
├─ created_at
└─ UNIQUE(user_id, friend_id)

friend_requests
├─ id (PK)
├─ sender_id (FK → auth_user)
├─ receiver_id (FK → auth_user)
├─ status ('pending' | 'accepted' | 'rejected')
├─ created_at
├─ updated_at
└─ UNIQUE(sender_id, receiver_id)
```

## Główne uproszczenia vs v1

### 1. Tournaments - tylko 2 typy zamiast 6
- ✅ Round Robin (liga)
- ✅ Single Elimination (puchar)
- ❌ Double Elimination
- ❌ Ladder
- ❌ Americano/Mexicano
- ❌ Swiss System

### 2. No GenericForeignKey
- Usunięto `content_type` / `object_id` z Activities
- Uproszczona struktura bez ContentType

### 3. Simplified Tournament Matches
- Tylko podstawowe pola (3 sety max)
- Bez `MatchScoreHistory` (na razie)
- Bez `MatchReaction` (emoji - nice to have)
- Bez `ChallengeRejection` (tylko dla Ladder)

### 4. No Chat
- Całkowicie pominięty w v1
- `ChatMessage`, `ChatImage`, `TournamentMatchChatMessage` → v2

### 5. No Garmin
- Pominięto encrypted fields w Profile
- Brak `Activity`, `TennisData`

### 6. Simplified Notifications
- Tylko podstawowe: title, message, link, is_read
- Bez integracji z Web Push API (na razie)

## NocoDB - Strategia uprawnień

### Read-Only Tables:
- `ranking_history` - historia generowana przez Django
- `tournament_matches` - wyniki generowane przez system
- `notifications` - tylko Django tworzy

### Editable Tables:
- `reservations` - admin może zmieniać statusy
- `tournaments` - admin zarządza turniejami
- `tournament_participants` - admin może dodawać/usuwać
- `facilities` / `courts` - admin zarządza obiektami

### Hidden from NocoDB:
- `auth_user` / `auth_*` - tylko przez Django Admin
- Sensitive data

## Migracja z MySQL → PostgreSQL

### NIE robimy migracji danych
- Stara baza była testowa
- Zaczynamy z czystą bazą PostgreSQL
- Nowe ID, nowe dane produkcyjne

### Workflow:
1. Deploy PostgreSQL na OVH
2. `python manage.py migrate` (nowe tabele)
3. `python manage.py createsuperuser`
4. Ręczne dodanie podstawowych danych (facilities, courts, rank points)
5. Podłączenie NocoDB do tej samej bazy

## Kolejne kroki

1. ✅ Design modeli (ten dokument)
2. ⏳ Implementacja modeli Django
3. ⏳ Konfiguracja settings.py (PostgreSQL + psycopg)
4. ⏳ Migracje
5. ⏳ Konfiguracja NocoDB
6. ⏳ Deploy na OVH
