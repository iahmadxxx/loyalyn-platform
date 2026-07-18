#!/usr/bin/env bash
set -euo pipefail
umask 077
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/opt/loyalyn-backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OBSOLETE_MIGRATION="backend/alembic/versions/0005_single_brand_studio.py"
EXPECTED_HEAD="0006_single_brand_studio"

cd "$PROJECT_DIR"
[ -f .env ] || { echo "ERROR: $PROJECT_DIR/.env is missing"; exit 1; }
docker compose config >/dev/null
mkdir -p "$BACKUP_DIR"

echo "[1/9] Saving current revision and files"
git rev-parse HEAD > "$BACKUP_DIR/commit-$STAMP.txt" 2>/dev/null || echo "not-a-git-checkout" > "$BACKUP_DIR/commit-$STAMP.txt"
tar --exclude='loyalyn/.git' --exclude='loyalyn/frontend/node_modules' --exclude='loyalyn/frontend/.next' --exclude='*/__pycache__' --exclude='*/.pytest_cache' -C "$(dirname "$PROJECT_DIR")" -czf "$BACKUP_DIR/files-$STAMP.tar.gz" "$(basename "$PROJECT_DIR")"

echo "[2/9] Dumping PostgreSQL"
docker compose exec -T db sh -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$BACKUP_DIR/database-$STAMP.sql"
test -s "$BACKUP_DIR/database-$STAMP.sql"

echo "[3/9] Updating repository"
if [ -d .git ]; then git pull --ff-only; fi

echo "[4/9] Removing obsolete v6.0.0 migration branch"
if [ -f "$OBSOLETE_MIGRATION" ]; then
  echo "Removing conflicting file: $OBSOLETE_MIGRATION"
  rm -f "$OBSOLETE_MIGRATION"
fi
find backend/alembic/versions -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true

echo "[5/9] Preparing Alembic version storage"
docker compose exec -T db sh -lc 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'alembic_version' AND column_name = 'version_num'
  ) THEN
    ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128);
  END IF;
END $$;
SQL

echo "[6/9] Building containers"
docker compose build --pull

echo "[7/9] Verifying a single Alembic head and applying migrations"
docker compose stop api worker web >/dev/null 2>&1 || true
docker compose up -d db
HEAD_OUTPUT="$(docker compose run --rm --no-deps api alembic heads)"
printf '%s\n' "$HEAD_OUTPUT"
HEAD_COUNT="$(printf '%s\n' "$HEAD_OUTPUT" | grep -c '(head)' || true)"
if [ "$HEAD_COUNT" -ne 1 ] || ! printf '%s\n' "$HEAD_OUTPUT" | grep -q "^${EXPECTED_HEAD} (head)$"; then
  echo "ERROR: Alembic migration graph is not the expected single head: $EXPECTED_HEAD"
  echo "Check backend/alembic/versions and remove the obsolete 0005_single_brand_studio.py file."
  exit 1
fi
docker compose run --rm --no-deps api alembic upgrade "$EXPECTED_HEAD"

echo "[8/9] Starting services and waiting for health checks"
docker compose up -d --remove-orphans
"$PROJECT_DIR/deploy/healthcheck.sh"

echo "[9/9] Upgrade complete"
echo "Database backup: $BACKUP_DIR/database-$STAMP.sql"
echo "Files backup:    $BACKUP_DIR/files-$STAMP.tar.gz"
