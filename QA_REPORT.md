# Loyalyn 5.0.0 QA Report

## Backend unit tests

```bash
PYTHONPATH=backend pytest -q backend/tests
```

Result: **19 passed**.

## V5 card-template workflow

```bash
PYTHONPATH=backend python scripts/qa_card_templates.py
```

Verified:

- one active main card per customer;
- multiple independent stamp programs inside one card;
- multiple templates in one brand;
- draft changes do not leak before publication;
- safe stamp reversal and preserved audit history;
- archive, restore and safe-delete behavior;
- rejection of a stamp program outside the customer's assigned template.

## Existing-platform regressions

The following all passed:

```bash
PYTHONPATH=backend python scripts/qa_smoke.py
PYTHONPATH=backend python scripts/qa_stamp_experience.py
PYTHONPATH=backend python scripts/qa_public_wallet_join.py
PYTHONPATH=backend python scripts/qa_security_sessions.py
PYTHONPATH=backend python scripts/qa_legacy_migration.py
```

These cover tenant isolation, multi-brand access, employee branch scope/privacy, feature gates, Coffee/Sweet balances, public join, real signed test `.pkpass` delivery, secure sessions, CSRF/logout revocation and preservation of legacy users/customer balances.

## Alembic

- Legacy schema upgraded successfully through `0004_card_templates`.
- A clean isolated database upgraded to head `0004_card_templates`.
- Clean schema contained **30 tables** and all V5 card/assignment/transaction tables.
- Migration 0004 includes existence guards because the original foundation migration bootstraps old databases from current metadata.

## Frontend

```bash
cd frontend
npm run lint
NEXT_PUBLIC_API_URL=https://api.loyalyn.site npm run build
```

- TypeScript validation passed.
- Next.js 15.4.10 production build passed.
- Generated routes include `/admin`, `/employee`, `/join/[slug]`, `/card/[token]` and `/login`.
- OpenAPI reports version `5.0.0` with **79 paths**.

## Responsive acceptance

The release contains the automated Playwright mobile smoke test (`scripts/qa_mobile_ui.py`) and the responsive styles/components for the V5 Cards, Programs, Wallet and Fast Scan screens. The current build environment blocked Chromium navigation to local/private addresses by administrator policy, so the final browser-device acceptance must be run against the deployed test URL. This limitation does not affect the successful TypeScript or production build results.

## External acceptance still required

A real Apple Pass Type certificate, matching WWDR certificate and physical iPhone are required for final Wallet installation and live APNs verification. No Apple private credential is embedded in the release archive.
