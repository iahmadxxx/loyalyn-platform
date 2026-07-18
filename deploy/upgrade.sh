#!/usr/bin/env bash
set -euo pipefail
umask 077
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/opt/loyalyn-backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"

cd "$PROJECT_DIR"
[ -f .env ] || { echo "ERROR: $PROJECT_DIR/.env is missing"; exit 1; }
docker compose config >/dev/null
mkdir -p "$BACKUP_DIR"

echo "[1/7] Saving current revision and files"
git rev-parse HEAD > "$BACKUP_DIR/commit-$STAMP.txt" 2>/dev/null || echo "not-a-git-checkout" > "$BACKUP_DIR/commit-$STAMP.txt"
tar --exclude='loyalyn/.git' --exclude='loyalyn/frontend/node_modules' --exclude='loyalyn/frontend/.next' --exclude='*/__pycache__' --exclude='*/.pytest_cache' -C "$(dirname "$PROJECT_DIR")" -czf "$BACKUP_DIR/files-$STAMP.tar.gz" "$(basename "$PROJECT_DIR")"

echo "[2/7] Dumping PostgreSQL"
docker compose exec -T db sh -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$BACKUP_DIR/database-$STAMP.sql"
test -s "$BACKUP_DIR/database-$STAMP.sql"

echo "[3/7] Updating repository"
if [ -d .git ]; then git pull --ff-only; fi

echo "[4/7] Building containers"
docker compose build --pull

echo "[5/7] Starting services and applying Alembic migrations"
docker compose up -d --remove-orphans

echo "[6/7] Waiting for health checks"
"$PROJECT_DIR/deploy/healthcheck.sh"

echo "[7/7] Upgrade complete"
echo "Database backup: $BACKUP_DIR/database-$STAMP.sql"
echo "Files backup:    $BACKUP_DIR/files-$STAMP.tar.gz"
