# Upgrade an existing Loyalyn installation to 4.1.0

Version 4.1 preserves the current PostgreSQL volume and all V4 program profiles, stamp cards, customers, balances, Wallet designs and audit history. It adds secure server-side sessions, scoped employee permissions and responsive mobile administration.

## Recommended upgrade

After uploading the 4.1 files to the existing Git repository:

```bash
cd /opt/loyalyn
git fetch origin
git reset --hard origin/main

test -f frontend/.npmrc && echo "OK - .npmrc exists"
chmod +x deploy.sh deploy/*.sh
sudo ./deploy/upgrade.sh
```

The script:

1. validates `.env` and Docker Compose;
2. records the current revision;
3. creates a PostgreSQL dump and source archive under `/opt/loyalyn-backups`;
4. rebuilds `api`, `worker` and `web`;
5. runs Alembic through revision `0003_security_sessions`;
6. starts services without deleting the database volume;
7. retries API/frontend health checks while the containers start.

Never use:

```bash
docker compose down -v
```

## Expected sign-in behavior

The old browser token was stored in `localStorage`. Version 4.1 uses Secure HttpOnly cookies and a server-side session. Existing accounts and passwords remain unchanged, but users should sign in once after the upgrade.

## Data behavior

- Existing brands and all historical loyalty data remain intact.
- Existing V4 brand program modes and feature flags remain unchanged.
- Disabling a feature hides and blocks it but never deletes its records.
- Employees remain linked to their brands/branches; effective role defaults are applied when custom permissions are empty.

## Post-upgrade verification

```bash
cd /opt/loyalyn
docker compose ps
curl -sS https://api.loyalyn.site/api/health && echo
curl -I https://app.loyalyn.site
```

Then verify:

1. sign in with the existing platform-owner account;
2. open Overview, Customers, Branches and Employees directly after login—no black screen should occur;
3. test the same navigation on a phone or a 390px browser viewport;
4. sign in as a branch employee and confirm only authorized sections/actions appear;
5. search for a customer and confirm the full customer directory is not loaded for the default employee;
6. open Fast Scan and confirm the assigned branch is selected automatically;
7. add and redeem a test stamp card transaction;
8. save and publish a Wallet design;
9. confirm a brand manager cannot open the central Apple certificate page;
10. confirm logout returns to the login page and the old session cannot be reused.

A hard refresh is not normally required because the new build changes the static assets, but clearing a stale browser tab after deployment is harmless.
