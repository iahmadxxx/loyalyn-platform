# Upgrade an existing Loyalyn installation to 3.0.0

The migration is designed to keep the current PostgreSQL named volume and add missing V3 tables/columns.

## Recommended command

From `/opt/loyalyn` after the new files are in Git:

```bash
sudo ./deploy/upgrade.sh
```

The script:

1. validates `.env` and Docker Compose;
2. records the current Git commit;
3. creates `/opt/loyalyn-backups/database-<timestamp>.sql`;
4. creates `/opt/loyalyn-backups/files-<timestamp>.tar.gz`;
5. pulls the current branch when the folder is a Git checkout;
6. rebuilds and starts API, worker, web and database without deleting volumes;
7. waits for API and frontend health checks.

## Manual equivalent

```bash
cd /opt/loyalyn
mkdir -p /opt/loyalyn-backups
STAMP=$(date +%Y%m%d-%H%M%S)
docker compose exec -T db sh -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  > "/opt/loyalyn-backups/database-$STAMP.sql"
docker compose up -d --build --remove-orphans
curl --retry 20 --retry-delay 3 --fail http://127.0.0.1:8000/api/health
```

Do not use `docker compose down -v`.

## Post-upgrade checks

- Sign in with the existing platform-owner account.
- Create a test brand and manager.
- Sign in as that manager and confirm only the assigned brand is visible.
- Create a customer and apply a visit.
- Save and publish a Wallet design.
- Upload the real central certificate as platform owner, then issue a test card.
- Send an in-app campaign and verify recipient counters.
