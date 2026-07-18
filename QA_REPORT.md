# Loyalyn 3.0.0 QA Report

Automated checks included in the release:

## Backend unit and cryptographic tests

```bash
PYTHONPATH=backend pytest -q backend/tests
```

Release result: **11 passed**.

Coverage includes:

- points, stamps and cashback calculations, multiplier caps and normal/overnight time windows;
- encryption round-trip;
- test-certificate extraction and identifier checks;
- private-key/certificate matching;
- signed pkpass ZIP contents, pass JSON, manifest and signature generation.

## API end-to-end smoke test

```bash
PYTHONPATH=backend python scripts/qa_smoke.py
```

The isolated scenario verifies:

- platform-owner and brand-manager sign-in;
- two-brand tenant isolation;
- one manager assigned to multiple brands without password takeover;
- central Wallet certificate endpoint denied to brand managers;
- branch ownership validation and cross-brand branch rejection;
- employee restrictions;
- customer creation and home-branch assignment;
- idempotent visits, spend, point and stamp operations;
- stamp reward earning, redemption and reversal;
- reward stock redemption and reversal;
- coupon creation, editing, redemption and duplicate protection;
- tier editing;
- Wallet publishing blocked until the central certificate exists;
- campaigns for all customers, one branch, selected customers and customers with a ready reward;
- audience isolation, in-app delivery and customer inboxes;
- audit records.

Latest release run completed with **2 brands**, **2 manager brand memberships**, **23 audit entries** and all security assertions passing.

## Legacy database migration test

```bash
PYTHONPATH=backend python scripts/qa_legacy_migration.py
```

The test creates a legacy MVP database, runs Alembic to the current head and verifies that:

- legacy users are mapped to `platform_owner` and `brand_admin` correctly;
- the old customer and balance are preserved;
- brand access is backfilled;
- the default Wallet design and four membership tiers are created;
- the existing loyalty program is preserved.

## Frontend production build

```bash
cd frontend
npm ci
npx tsc --noEmit
npm run build
```

The production build passed on Next.js 15.4.10 and generated the `/admin`, `/login`, `/employee`, `/join` and customer-card routes.

## Static release checks

- OpenAPI: version `3.0.0`, 47 paths.
- Docker Compose YAML: `db`, `api`, `worker`, `web` parsed successfully.
- Deployment and rollback shell scripts passed `bash -n`.

## External acceptance still required

A production Apple Pass Type certificate, Apple WWDR certificate and physical iPhone are required to validate installation into Apple Wallet and live APNs delivery. No real private Apple certificate is embedded in this release. Cryptographic package generation is tested with an isolated test certificate.
