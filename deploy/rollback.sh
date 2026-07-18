#!/usr/bin/env bash
set -euo pipefail
umask 077
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DB_BACKUP="${1:-}"
FILES_BACKUP="${2:-}"

if [ -z "$DB_BACKUP" ] || [ -z "$FILES_BACKUP" ]; then
  echo "Usage: CONFIRM_RESTORE=YES sudo $0 /opt/loyalyn-backups/database-TIMESTAMP.sql /opt/loyalyn-backups/files-TIMESTAMP.tar.gz"
  exit 1
fi
[ "${CONFIRM_RESTORE:-}" = "YES" ] || { echo "Set CONFIRM_RESTORE=YES to continue"; exit 1; }
[ -s "$DB_BACKUP" ] || { echo "Database backup not found or empty"; exit 1; }
[ -s "$FILES_BACKUP" ] || { echo "Files backup not found or empty"; exit 1; }

cd "$PROJECT_DIR"
docker compose down
mv "$PROJECT_DIR" "${PROJECT_DIR}-failed-$(date +%Y%m%d-%H%M%S)"
tar -C "$(dirname "$PROJECT_DIR")" -xzf "$FILES_BACKUP"
cd "$PROJECT_DIR"
docker compose up -d db
for _ in $(seq 1 30); do docker compose exec -T db sh -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' && break; sleep 2; done
docker compose exec -T db sh -lc 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" "$POSTGRES_DB" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"'
docker compose exec -T db sh -lc 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" "$POSTGRES_DB"' < "$DB_BACKUP"
docker compose up -d --build --remove-orphans
"$PROJECT_DIR/deploy/healthcheck.sh"
echo "Rollback complete. Failed release retained beside $PROJECT_DIR."
