# GitHub Actions → OVH — jak działa automatyczny deploy

## Skrót

Push na branch `OVHTennis` = automatyczny deploy na produkcję (`portal.raketon.pl`).
Nic więcej nie trzeba robić ręcznie.

---

## Przepływ krok po kroku

```
git push origin OVHTennis
       │
       ▼
GitHub Actions (ubuntu-latest)
  1. Checkout repozytorium
  2. Uruchom SSH agent z kluczem z Secrets
  3. Dodaj serwer OVH do known_hosts
  4. ssh deploy@serwer "bash /opt/apps/tennis-club/deploy.sh"
       │
       ▼
deploy.sh na serwerze OVH (9 kroków):
  [1/9] git fetch origin OVHTennis
  [2/9] git checkout OVHTennis && git reset --hard origin/OVHTennis
  [3/9] docker compose up -d --build   ← przebudowuje kontenery (Astro build wewnątrz)
  [4/9] czeka aż kontener tennis-web wystartuje
  [5/9] health check — czeka aż https://tennis.mediprima.pl/health/ odpowie
  [6/9] python manage.py migrate       ← uruchamia migracje Django
  [7/9] python manage.py collectstatic
  [8/9] python manage.py check --deploy
  [9/9] końcowy health check
```

Cały proces trwa zwykle **2–4 minuty**.

---

## Plik workflow

`.github/workflows/deploy-ovh.yml` — wyzwala się przy każdym push na `OVHTennis`:

```yaml
on:
  push:
    branches:
      - OVHTennis
  workflow_dispatch:        # można też odpalić ręcznie z GitHub UI
```

`concurrency: cancel-in-progress: true` — jeśli dwa pushe wyjdą jeden po drugim,
drugi anuluje pierwszy deploy. Produkcja zawsze dostaje ostatnią wersję.

---

## Secrets w GitHub

Klucze potrzebne do działania (Settings → Secrets and variables → Actions):

| Secret | Co zawiera |
|--------|-----------|
| `OVH_SSH_KEY` | Prywatny klucz SSH do serwera |
| `OVH_HOST` | Adres IP lub hostname serwera |
| `OVH_USER` | Użytkownik SSH (np. `deploy`) |

---

## Branch model

| Branch | Rola |
|--------|------|
| `PatrickPinace` | Roboczy — tu commitujemy i testujemy lokalnie |
| `OVHTennis` | Produkcja — merge tu = automatyczny deploy |
| `Skorpi86` | Branch Lucjana — zmiany mergujemy selektywnie do `PatrickPinace` |

**Workflow:**
```
PatrickPinace  →  merge → OVHTennis  →  push  →  auto-deploy
```

Nigdy nie commituj bezpośrednio na `OVHTennis` — zawsze przez merge z `PatrickPinace`.

---

## Rollback

Jeśli coś się posypie na produkcji, na serwerze jest skrypt:

```bash
ssh ovh "bash /opt/apps/tennis-club/rollback.sh"
```

Przywraca poprzedni SHA Gita i przebudowuje kontenery.

---

## Migracje Django

`deploy.sh` uruchamia `python manage.py migrate` **automatycznie** w kroku [6/9].
Nie trzeba robić niczego ręcznie — każda nowa migracja w repozytorium wchodzi przy deploymencie.

Jeśli chcesz sprawdzić stan migracji na produkcji:

```bash
ssh ovh "docker exec tennis-web python manage.py showmigrations"
```

---

## Sprawdzenie logów deployu

```bash
ssh ovh "tail -50 /opt/apps/tennis-club/deploy.log"
```

Każdy deploy zapisuje logi do tego pliku z timestampem.

---

## Ręczne odpalenie deployu (bez pusha)

Z GitHub UI: Actions → Deploy OVH Tennis → Run workflow → Branch: OVHTennis → Run.

Lub z terminala (wymaga `gh` CLI):

```bash
gh workflow run deploy-ovh.yml --ref OVHTennis
```
