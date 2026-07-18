# Loyalyn 4.1.0 QA Report

## Backend unit and cryptographic tests

```bash
PYTHONPATH=backend pytest -q backend/tests
```

Release result: **15 passed**.

Coverage includes program profiles, points/stamps/cashback rules, caps and time windows, encryption, Apple certificate/key validation and signed `.pkpass` manifest/signature generation.

## Existing-platform API smoke test

```bash
PYTHONPATH=backend python scripts/qa_smoke.py
```

Result: passed with two isolated brands, multi-brand manager access, audit records, tenant isolation, central-Wallet restriction, branch enforcement, employee customer privacy and campaign audience isolation.

## Stamp-experience end-to-end test

```bash
PYTHONPATH=backend python scripts/qa_stamp_experience.py
```

Verified independent Coffee and Sweet balances/rewards, stable public registration QR, self-enrollment, selected-card stamp issue and redemption, duplicate-action protection, server-side feature gates and preservation of stamp history after changing the brand profile.

## Secure-session test

```bash
PYTHONPATH=backend python scripts/qa_security_sessions.py
```

Verified:

- Secure HttpOnly access and refresh cookies;
- rotating refresh tokens and replay rejection;
- CSRF enforcement;
- logout revocation of a previously captured access token;
- permission revocation and password-change invalidation of existing employee sessions in the API smoke test;
- production security headers.

## Database migration tests

```bash
PYTHONPATH=backend python scripts/qa_legacy_migration.py
```

The legacy MVP schema upgrades through revisions `0001`, `0002` and `0003` while preserving users, roles and customer balances. A fresh empty database upgraded to the current Alembic head and created **27 tables**, including `auth_sessions`.

## Frontend production checks

```bash
cd frontend
npm run lint
NEXT_PUBLIC_API_URL=https://api.loyalyn.site npm run build
```

TypeScript validation and the Next.js 15.4.10 production build passed. Generated routes include `/admin`, `/employee`, `/join/[slug]`, `/card/[token]` and `/login`.

## Browser and responsive QA

Playwright/Chromium checks were run against an isolated local database:

- platform owner opened all **12** administration sections on 390×844 mobile and 1440×1000 desktop;
- no client-side exception or horizontal mobile overflow occurred;
- visible mobile buttons met the touch-target check and visible form fields used mobile-safe font sizing;
- employee navigation showed only **Overview, Customers and Fast Scan** with the default cashier permissions;
- restricted customer edit/history/manual-adjustment buttons were absent for the cashier, while allowed operational actions remained visible;
- the staff permission editor showed correct employee/manager defaults and effective permissions for legacy empty permission objects;
- employee customer search returned privacy-limited data;
- the assigned branch was selected automatically in Fast Scan;
- the dashboard, stamp cards, Fast Scan and Wallet Studio were visually captured on mobile.

## Regression fixed

The previous dashboard branch count can no longer be reused as a branch array. Branch option lists have independent array state, all API list results are normalized, optional requests use settled loading, and a per-section error boundary prevents a failed panel from taking down the whole app.

## Static/release checks

- Python source compilation passed.
- OpenAPI reports version `4.1.0` with **65 paths**.
- Deployment and rollback shell scripts pass syntax checks.
- The npm lockfile contains no private/internal registry URL.
- Release archives exclude `.env`, certificates, caches, `node_modules` and `.next`.

## External acceptance still required

A production Apple Pass Type certificate, matching WWDR certificate and a physical iPhone are still required for final installation and live APNs testing. No real Apple private credential is embedded in the release.
