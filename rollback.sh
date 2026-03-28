#!/usr/bin/env bash
set -Eeuo pipefail

APP_ROOT="/opt/apps/tennis-club"
APP_DIR="$APP_ROOT/app"
LOG_FILE="$APP_ROOT/deploy.log"
PREV_SHA_FILE="$APP_ROOT/.previous_deploy_sha"
WEB_CONTAINER="tennis-web"
HEALTH_URL="https://tennis.mediprima.pl/health/"
MAX_WAIT=120

exec > >(tee -a "$LOG_FILE") 2>&1

echo "=================================================="
echo "ROLLBACK START: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=================================================="

if [ ! -f "$PREV_SHA_FILE" ]; then
  echo "No previous SHA file found: $PREV_SHA_FILE"
  exit 1
fi

TARGET_SHA="$(cat "$PREV_SHA_FILE")"
if [ -z "$TARGET_SHA" ]; then
  echo "Previous SHA file is empty"
  exit 1
fi

cd "$APP_DIR"

echo "Fetching repository state"
git fetch --all

echo "Rolling back to SHA: $TARGET_SHA"
git checkout "$TARGET_SHA"

echo "Rebuilding and restarting containers"
docker compose up -d --build

echo "Running migrations"
docker exec "$WEB_CONTAINER" python manage.py migrate --settings=core.settings_v2

echo "Collecting static files"
docker exec "$WEB_CONTAINER" python manage.py collectstatic --noinput --settings=core.settings_v2

echo "Running Django deployment checks"
docker exec "$WEB_CONTAINER" python manage.py check --deploy --settings=core.settings_v2

echo "Waiting for health endpoint"
START_TS=$(date +%s)
until curl -fsS "$HEALTH_URL" >/dev/null 2>&1; do
  NOW_TS=$(date +%s)
  ELAPSED=$((NOW_TS - START_TS))
  if [ "$ELAPSED" -ge "$MAX_WAIT" ]; then
    echo "Rollback health check failed after ${MAX_WAIT}s"
    exit 1
  fi
  echo "Health not ready yet... (${ELAPSED}s)"
  sleep 3
done

echo "Rollback successful to SHA: $TARGET_SHA"
echo "ROLLBACK END: $(date '+%Y-%m-%d %H:%M:%S')"
echo
