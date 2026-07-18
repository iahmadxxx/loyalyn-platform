# Loyalyn 2.0 Deployment

This release keeps the existing PostgreSQL volume and creates the new V2 tables automatically at API startup.

## Server update

1. Back up the database:

```bash
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > /opt/loyalyn-before-v2.sql
```

2. Replace the project files but keep `.env` unchanged.

3. Build and start:

```bash
cd /opt/loyalyn
docker compose down
docker compose build --no-cache
docker compose up -d
```

4. Verify:

```bash
docker compose ps
curl -i https://api.loyalyn.site/api/health
```

## V2 modules

- Multi-brand selector and brand-scoped API access
- Branches
- Employees and roles
- Customers, points, stamps and card issuing
- Membership tiers
- Stamp programs
- Rewards and redemption API
- Wallet certificate upload storage
- Public customer card endpoint
- Notifications
- Audit log
- Expanded responsive Arabic dashboard

## Apple Wallet note

Certificate upload and pass records are implemented. Generating a signed `.pkpass` requires the real Apple Pass Type certificate, its password, Team ID, Pass Type ID and WWDR certificate. These secrets are intentionally not embedded in the project.
