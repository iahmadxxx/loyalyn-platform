# Upgrade an existing Loyalyn installation to 5.0.0

Version 5 preserves the PostgreSQL volume and all existing brands, customers, users, permissions, balances, stamp history, Wallet configuration, campaigns and audit records. It adds card templates, ordered template-program links, customer card assignment and reversible stamp transactions.

## Recommended upgrade

After uploading the V5 files to the existing repository:

```bash
cd /opt/loyalyn
git fetch origin
git reset --hard origin/main

cat VERSION
test -f frontend/.npmrc && echo "OK - .npmrc exists"
chmod +x deploy.sh deploy/*.sh
sudo ./deploy/upgrade.sh
```

Expected version:

```text
5.0.0
```

The upgrade script:

1. validates `.env` and Docker Compose;
2. records the current Git revision;
3. creates source and PostgreSQL backups under `/opt/loyalyn-backups`;
4. widens `alembic_version.version_num` to `VARCHAR(128)` when the table exists;
5. builds API, worker and web images;
6. applies Alembic through `0004_card_templates`;
7. starts services without deleting named volumes;
8. waits for API and frontend health checks.

Never run:

```bash
docker compose down -v
```

## Data migration behavior

- Existing brands receive a default published card template when first needed.
- Existing stamp programs remain available and are linked compatibly to the default template.
- Existing customer stamp balances and transactions are preserved.
- New template assignments do not create duplicate customer records.
- Archived templates/programs retain historical references.

## Post-upgrade checks

```bash
cd /opt/loyalyn
docker compose ps
curl -sS https://api.loyalyn.site/api/health && echo
curl -I https://app.loyalyn.site

docker compose exec -T db psql \
  -U "${POSTGRES_USER:-loyalyn}" \
  -d "${POSTGRES_DB:-loyalyn}" \
  -c "SELECT version_num FROM alembic_version;"
```

Expected Alembic head:

```text
0004_card_templates
```

Then verify in the UI:

1. create a Coffee-only card template;
2. create a Coffee + Sweet template and order both programs;
3. save draft changes and confirm customers still see the published version;
4. publish the template;
5. enroll a test customer from the public QR;
6. scan the customer and add one Coffee stamp;
7. reverse the accidental test operation and confirm the exact previous value returns;
8. confirm a program outside the assigned card cannot be stamped;
9. test Cards, Programs, Fast Scan and Wallet Studio on a phone;
10. upload/test the real Apple certificate only from the platform-owner account.
