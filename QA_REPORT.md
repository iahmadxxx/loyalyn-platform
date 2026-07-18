# Loyalyn 6.0.0 QA Report

## Backend unit tests

```bash
cd backend
PYTHONPATH=. pytest -q
```

Result: **19 passed**.

## V6 single-brand and multi-card workflow

```bash
PYTHONPATH=backend python scripts/qa_single_brand_studio.py
```

Verified:

- public registration can complete before card assignment;
- an admin-created customer can start with no card;
- Coffee, Sweet and Coffee + Sweet cards can all stay active for one customer;
- every card produces a distinct Wallet pass/link;
- the combination pass contains both independent programs;
- uploaded oversized stamp artwork is rendered into the fixed Wallet strip;
- generated `.pkpass` files contain valid signed ZIP payloads, `strip.png` at `375×123` and `strip@2x.png` at `750×246`;
- removing one assignment keeps the remaining cards active.

## Regression suites

All passed:

```bash
PYTHONPATH=backend python scripts/qa_card_templates.py
PYTHONPATH=backend python scripts/qa_stamp_experience.py
PYTHONPATH=backend python scripts/qa_public_wallet_join.py
PYTHONPATH=backend python scripts/qa_security_sessions.py
PYTHONPATH=backend python scripts/qa_smoke.py
PYTHONPATH=backend python scripts/qa_legacy_migration.py
```

Coverage includes tenant isolation, branch/employee permissions, public legacy join compatibility, signed test `.pkpass` delivery, secure cookies/CSRF/logout, reversible stamp operations and upgrading an old database through the new migration.

## Alembic

Legacy SQLite migration QA successfully upgraded through:

```text
0001_loyalyn_v3
0002_program_profiles_stamp_experience
0003_security_sessions
0004_card_templates
0005_single_brand_studio
```

## Frontend

```bash
cd frontend
npm run lint
npm run build
```

- TypeScript validation passed.
- Next.js 15.4.10 production build passed.
- Generated routes include `/admin`, `/join/[slug]`, `/card/[token]`, `/employee` and `/login`.
- OpenAPI reports version `6.0.0` with **84 paths**.

## Browser and Apple acceptance

The current execution environment blocks Chromium from navigating to localhost with `ERR_BLOCKED_BY_ADMINISTRATOR`, so a real interactive browser screenshot run could not be completed here. The successful production build does not replace final device acceptance.

A real Apple Pass Type certificate, matching WWDR certificate and physical iPhone are required to verify installation and production APNs updates. No private Apple credential is included in the archive.
