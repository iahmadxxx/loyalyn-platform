# Loyalyn 3.0.0

Loyalyn is a multi-brand loyalty operating system built with FastAPI, PostgreSQL, Next.js and Docker Compose.

## Delivered scope

- Platform owner creates brands and assigns one or more brand managers.
- Brand managers sign in through the same dashboard and see only their authorized brands.
- Branches, employees, customers, customer home-branch assignment and role-based brand isolation.
- A server-side loyalty engine for points, stamps, hybrid programs and cashback.
- Tier multipliers, birthday/referral bonuses, daily caps, point expiry, coupons, rewards, idempotent ledger entries and safe reversals.
- Wallet Studio with draft/publish workflow, logo/hero uploads, field controls and customer pass issuance.
- One central Apple Wallet certificate controlled only by the platform owner.
- Signed `.pkpass` generation and Apple Wallet device registration/update web-service endpoints.
- Campaigns, templates, scheduling, recurrence, branch/selected/reward-ready audience filters, delivery counters, retries and a separate worker.
- Arabic RTL administration interface with edit modals, loading states, validation and visible API errors.
- Audit log and database migrations.

## Local verification

```bash
cd backend
PYTHONPATH=. pytest -q
cd ..
PYTHONPATH=backend python scripts/qa_smoke.py
PYTHONPATH=backend python scripts/qa_legacy_migration.py
cd frontend
npm ci
npm run build
```

The smoke test uses an isolated SQLite file under `/tmp` and does not touch production data.

## First deployment

```bash
cp .env.example .env
chmod 600 .env
# Replace every CHANGE_ME value first.
./deploy.sh
```

Check:

```bash
docker compose ps
curl -fsS http://127.0.0.1:8000/api/health
curl -I http://127.0.0.1:3000
```

Place Nginx in front of ports `3000` and `8000`; keep both ports bound to `127.0.0.1` as configured.

## Apple Wallet

Only the platform owner sees **شهادة Apple المركزية**. Upload:

- Pass Type certificate `.p12`
- its password
- Apple WWDR certificate
- matching Pass Type Identifier
- matching Team Identifier

The backend checks the private key/certificate match, subject identifiers and expiry before activating the credential. Brand managers never receive certificate files or passwords; they publish a design and issue customer cards through the central signer.

A real certificate and an iPhone are still required for the final Apple-device acceptance test.

## Safe updates

Use:

```bash
sudo ./deploy/upgrade.sh
```

It creates a database dump and source archive before rebuilding. Never run `docker compose down -v` on production because it removes named volumes.
