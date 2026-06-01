# Tennis Club — Frontend (Astro + Tailwind)

MVP scaffold frontendu — inicjalny etap migracji z Django Templates do Astro.

## Stack

- **Astro 4** — framework (output: static / hybridowy)
- **Tailwind CSS 3** — utility classes z tokenami z design systemu
- **TypeScript** — strict mode
- **Django** — backend API (JWT auth przez `apps/api/`)

## Uruchomienie

```bash
cd frontend-astro
npm install
npm run dev        # dev server na http://localhost:4321
npm run build      # build do dist/
npm run preview    # podgląd buildu
```

## Routing

| Ścieżka Astro            | Odpowiednik Django          | Status      |
|--------------------------|------------------------------|-------------|
| `/dashboard`             | `GET /dashboard/`            | Placeholder |
| `/rankings`              | `GET /rankings/`             | Placeholder |
| `/tournaments`           | `GET /tournaments/`          | Placeholder |
| `/courts/reservations`   | `GET /courts/reservations/`  | Placeholder |

## Dostępne endpointy Django API

| Endpoint                          | Opis                    | Dostępny |
|-----------------------------------|-------------------------|----------|
| `POST /api/token/`                | JWT login               | ✅ (zakomentowany w urls.py) |
| `GET /api/me/`                    | Dane zalogowanego usera | ✅ |
| `GET /api/tournaments/`           | Lista turniejów         | ✅ |
| `GET /api/matches/history/`       | Historia meczy          | ✅ |
| `GET /api/notifications/`         | Powiadomienia           | ✅ |
| `GET /api/rankings/`              | Ranking graczy          | ❌ do implementacji |
| `GET /api/dashboard/summary/`     | Dane dashboardu         | ❌ do implementacji |
| `GET /api/courts/reservations/`   | Rezerwacje kortów       | ❌ do implementacji |

> **Uwaga:** `path('api/', ...)` jest zakomentowane w `core/urls.py` — odkomentuj przed podłączeniem.

## Design System

Tokeny CSS przepisane z `static/css/ui/tokens.css` do `src/styles/global.css`.
Tailwind odczytuje je przez `var(--token-name)`.

Dark mode domyślny — `localStorage.tc-theme` + `data-theme` na `<html>`.

## Następne kroki (poza MVP)

1. Odkomentować `path('api/', ...)` w Django `core/urls.py`
2. Zaimplementować `GET /api/rankings/` w Django
3. Podłączyć JWT auth w Astro (np. store w `localStorage` / cookie)
4. Zaimplementować widok Dashboard z prawdziwymi danymi
5. Komponent kalendarza kortów (FullCalendar lub custom grid)
