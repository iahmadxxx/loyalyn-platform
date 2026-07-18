# Upgrade Loyalyn to 6.0.1

Version 6 preserves the PostgreSQL volume, brands, customers, stamp balances, operations, employees, permissions, Wallet credentials and issued-pass history. It adds multi-card customer assignments, per-card Wallet passes and exact stamp presentation settings.

## Upgrade commands

After uploading the V6 files to GitHub:

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
6.0.1
```

Expected Alembic head:

```text
0006_single_brand_studio
```

The upgrade script creates source and PostgreSQL backups under `/opt/loyalyn-backups`, rebuilds API/worker/web and starts services without deleting named volumes.

Never run:

```bash
docker compose down -v
```

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

## Functional acceptance

1. Open `استوديو البطاقات`.
2. Create Coffee, Sweet and Coffee + Sweet cards.
3. Upload a wide or square custom stamp image and verify it remains inside its slot in the live preview.
4. Publish all three cards.
5. Register a customer without a card.
6. Open the customer and activate all three cards.
7. Issue each Wallet card and copy its individual link.
8. Scan the membership code and confirm all active cards appear together.
9. Add and reverse a test stamp.
10. Test a real pass on iPhone using the production Apple certificate.
