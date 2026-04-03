#!/usr/bin/env bash
set -Eeuo pipefail

APP_ROOT="/opt/apps/tennis-club"
APP_DIR="$APP_ROOT/app"
LOG_FILE="$APP_ROOT/deploy.log"
PREV_SHA_FILE="$APP_ROOT/.previous_deploy_sha"
BRANCH="OVHTennis"
WEB_CONTAINER="tennis-web"
HEALTH_URL="https://tennis.mediprima.pl/health/"
MAX_WAIT=120

mkdir -p "$APP_ROOT"
touch "$LOG_FILE"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "=================================================="
echo "DEPLOY START: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=================================================="

cd "$APP_DIR"

echo "[1/9] Fetching latest code"
git fetch origin "$BRANCH"

CURRENT_SHA="$(git rev-parse HEAD)"
echo "$CURRENT_SHA" > "$PREV_SHA_FILE"
echo "Saved previous SHA: $CURRENT_SHA"

echo "[2/9] Switching to branch $BRANCH"
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

NEW_SHA="$(git rev-parse HEAD)"
echo "Deploying SHA: $NEW_SHA"

echo "[3/9] Building and starting containers"
docker compose up -d --build

echo "[4/9] Waiting for container to be running"
for i in $(seq 1 30); do
  if docker ps --format '{{.Names}}' | grep -q "^${WEB_CONTAINER}$"; then
    echo "Container ${WEB_CONTAINER} is running"
    break
  fi
  sleep 2
done

echo "[5/9] Waiting for app health"
START_TS=$(date +%s)
until curl -fsS "$HEALTH_URL" >/dev/null 2>&1; do
  NOW_TS=$(date +%s)
  ELAPSED=$((NOW_TS - START_TS))
  if [ "$ELAPSED" -ge "$MAX_WAIT" ]; then
    echo "Health check failed after ${MAX_WAIT}s"
    exit 1
  fi
  echo "Health not ready yet... (${ELAPSED}s)"
  sleep 3
done
echo "Health endpoint is responding"

echo "[6/9] Running migrations"
docker exec "$WEB_CONTAINER" python manage.py migrate

echo "[7/9] Collecting static files"
docker exec "$WEB_CONTAINER" python manage.py collectstatic --noinput

echo "[8/9] Running Django deployment checks"
docker exec "$WEB_CONTAINER" python manage.py check --deploy

echo "[9/9] Final health verification"
curl -fsS "$HEALTH_URL" >/dev/null

echo "Deploy successful"
echo "Previous SHA: $CURRENT_SHA"
echo "Current  SHA: $NEW_SHA"
echo "DEPLOY END: $(date '+%Y-%m-%d %H:%M:%S')"
echo
