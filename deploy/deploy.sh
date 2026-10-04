#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR="${APP_DIR:-$HOME/ticket-booking}"
BRANCH="${BRANCH:-main}"
REPO_URL="${REPO_URL:-https://github.com/DEVENDRA-5470/ticket-booking.git}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1/api/health}"
LOCK="/tmp/ticketflow-deploy.lock"
LOG="$APP_DIR/deploy.log"
exec 9>"$LOCK"; flock -n 9 || exit 0
mkdir -p "$APP_DIR"; touch "$LOG"
exec > >(tee -a "$LOG") 2>&1
log(){ echo "[$(date '+%F %T')] $*"; }
die(){ log "ERROR: $*"; exit 1; }
command -v git >/dev/null || die "git missing"
command -v docker >/dev/null || die "docker missing"
docker compose version >/dev/null 2>&1 || die "docker compose missing"
cd "$APP_DIR"
if [ ! -d .git ]; then git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"; cd "$APP_DIR"; fi
[ -f .env ] || die ".env missing: create $APP_DIR/.env"
git remote set-url origin "$REPO_URL"
git fetch --prune origin "$BRANCH"
remote="$(git rev-parse origin/$BRANCH)"
current="$(git rev-parse HEAD)"
[ "$current" = "$remote" ] && [ "${FORCE_DEPLOY:-0}" != "1" ] && { log "No changes: $current"; exit 0; }
previous="$current"
rollback(){ log "ROLLBACK -> $previous"; git reset --hard "$previous" || true; docker compose up -d --build --remove-orphans || true; }
trap rollback ERR
log "Deploying $remote"
git reset --hard "origin/$BRANCH"
git clean -fd -e .env -e deploy.log
docker compose config >/dev/null
docker compose build --pull
docker compose up -d backend
for i in {1..30}; do docker inspect -f '{{.State.Running}}' ticketing-backend 2>/dev/null | grep -q true && break; sleep 2; done
docker compose exec -T backend alembic upgrade head
docker compose exec -T backend env PYTHONPATH=/app python /app/scripts/seed_events.py
docker compose exec -T backend env PYTHONPATH=/app python /app/scripts/seed_food.py
docker compose up -d --remove-orphans
for i in {1..45}; do curl -fsS --max-time 5 "$HEALTH_URL" >/tmp/ticketflow-health.json 2>/dev/null && break; sleep 2; done
curl -fsS --max-time 5 "$HEALTH_URL" >/tmp/ticketflow-health.json || die "health check failed"
trap - ERR
log "SUCCESS commit=$(git rev-parse HEAD) health=$(cat /tmp/ticketflow-health.json)"
docker compose ps
