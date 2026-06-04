# Mechanizm Budowy Astro (Google Analytics 4 w Dockerze)

Astro jest frameworkiem generującym statyczny kod po stronie klienta (lub serwera), co oznacza, że identyfikator śledzenia GA4 musi zostać wstrzyknięty do kodu w czasie budowania obrazu Docker, a nie w trakcie jego działania (runtime).

Proces ten jest w pełni zautomatyzowany poprzez konfigurację w plikach projektu:

### 1. Mapowanie zmiennej w [docker-compose.yml]
Podczas wywołania komendy budowania, Docker Compose odczytuje wartość `GA_MEASUREMENT_ID` z pliku `.env` i przekazuje ją jako argument budowania (`args`):

```yaml
astro-web:
  build:
    context: .
    dockerfile: Dockerfile.astro
    args:
      - ASTRO_BASE=/astro
      - PUBLIC_GA_MEASUREMENT_ID=${GA_MEASUREMENT_ID} # <-- Przekazanie wartości
```

### 2. Odbiór argumentu w [Dockerfile.astro]
W pliku `Dockerfile.astro` zdefiniowany argument jest przypisywany do zmiennej środowiskowej procesu budowania Astro:

```dockerfile
ARG PUBLIC_GA_MEASUREMENT_ID=
ENV PUBLIC_GA_MEASUREMENT_ID=$PUBLIC_GA_MEASUREMENT_ID
```

Dzięki prefiksowi `PUBLIC_`, Astro (Vite) poprawnie kompiluje kod frontendu i wstrzykuje identyfikator pomiaru do finalnych skryptów JS.
