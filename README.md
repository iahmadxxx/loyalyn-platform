# Loyalyn 5.1.0

Loyalyn is a multi-brand loyalty operating system built with FastAPI, PostgreSQL, Next.js and Docker Compose. Version 5 adds a complete card-template layer: one customer Wallet card can contain several independent stamp programs, while each brand can publish multiple card combinations such as Coffee only, Coffee + Sweet, Breakfast or VIP.

## Card templates

Each brand can create any number of card templates. A template controls:

- Arabic and English names, description, status and public-registration visibility;
- the ordered stamp programs included in that card;
- colors, logo, hero/strip/background artwork, barcode format and text fields;
- draft and published versions so unfinished changes never leak to customers;
- duplicate, publish, unpublish, archive, restore and safe-delete actions.

Existing brands receive a compatible default published template automatically. Existing customers and stamp balances are preserved.

## Multiple stamp programs in one card

A single customer card can display independent progress for Coffee, Sweet, Breakfast or any custom label. Each program has its own target, reward, icon, colors, branch rules and transaction history. The first programs appear on the Wallet face and all programs remain available in the customer card details.

## Customer assignment and public join

- Every customer has one active main card assignment per brand.
- The manager can change the customer's card template without creating a duplicate customer.
- The public brand QR shows only published templates that allow public registration.
- The customer selects a card, registers, receives a stable membership QR and—when Apple signing is ready—an Add to Apple Wallet action.

## Fast Scan and safe reversal

The employee scans the membership QR, sees only the programs included in that customer's selected card and adds the relevant Coffee/Sweet/etc. stamp. Every operation records before/after values, employee, branch and time.

A mistaken operation is reversed safely:

- the original audit row is retained;
- a compensating reversal row is created;
- only the latest unreversed operation for that program can be reversed;
- the exact previous balance is restored;
- unauthorized or cross-template stamping is rejected by the API.

## Full administration lifecycle

Card templates and stamp programs support create, edit, reorder, publish, disable, archive, restore and safe deletion. Records already used by customers are archived rather than destructively removed.

The existing Points only, Stamps only, Stamps + Points, Full Loyalty and Custom brand profiles remain available. Feature switches hide and reject disabled capabilities without deleting historical records.

## Mobile administration

The Arabic RTL interface includes a mobile header, slide-out navigation, bottom quick navigation, single-column forms, touch-friendly controls, responsive card previews and a simplified Fast Scan flow. TypeScript and the production Next.js build are part of the release checks.

## Apple Wallet ownership

Only the platform owner manages the central Apple certificate. Brand managers create and publish card designs but cannot read or download the certificate or password. A production Pass Type certificate, matching WWDR certificate and a physical iPhone are required for final live installation/APNs acceptance.

## Verification

```bash
PYTHONPATH=backend pytest -q backend/tests
PYTHONPATH=backend python scripts/qa_smoke.py
PYTHONPATH=backend python scripts/qa_stamp_experience.py
PYTHONPATH=backend python scripts/qa_public_wallet_join.py
PYTHONPATH=backend python scripts/qa_security_sessions.py
PYTHONPATH=backend python scripts/qa_legacy_migration.py
PYTHONPATH=backend python scripts/qa_card_templates.py

cd frontend
npm ci
npm run lint
NEXT_PUBLIC_API_URL=https://api.loyalyn.site npm run build
```

## Deployment

New installation:

```bash
cp .env.example .env
chmod 600 .env
# Replace every CHANGE_ME value.
./deploy.sh
```

Existing installation:

```bash
sudo ./deploy/upgrade.sh
```

The upgrade script creates PostgreSQL and source backups, widens Alembic revision storage when required, applies migrations and rebuilds the services without deleting named volumes. Never run `docker compose down -v` in production.
