# Loyalyn 6.0.1 — Single-Brand Stamp Studio

Loyalyn V6 is a focused Apple Wallet stamp-card system for one brand. The administration experience is intentionally small and direct: design cards, register customers, assign one or several cards, scan, and review operations.

The old platform data model remains upgrade-safe, but the main interface no longer exposes the multi-brand/SaaS, points, cashback and tier complexity.

## One live studio

The `استوديو البطاقات` page combines the full card workflow:

- create any number of cards;
- design and preview the selected card in the same screen;
- add Coffee, Sweet, Breakfast or any custom stamp program inside a card;
- edit colors, names, rewards, order and stamp count;
- upload the card logo/background and filled/empty stamp artwork;
- adjust stamp size, gap and X/Y position in exact pixels;
- save, publish, duplicate independently or archive;
- keep several published cards active at the same time.

Examples supported by the same brand:

- Coffee card;
- Sweet card;
- Coffee + Sweet card;
- any other custom combination.

## Deterministic stamp artwork

Apple Wallet controls the physical pass layout, so Loyalyn generates the stamp area as one dynamic strip image. Every uploaded stamp/logo is fitted inside a fixed slot. The renderer applies size, spacing, containment and X/Y offsets inside that slot, preventing artwork from jumping above or below the stamp row.

The same pass can show up to two stamp-program rows on the strip, with additional program details available in the Wallet fields/back information.

## Customer card assignment

A customer can start with no card. From one customer dialog the manager can:

- activate one card or several cards together;
- remove one card without affecting the rest;
- issue a separate Apple Wallet pass for every selected card;
- open the card page;
- copy the card link and send it to the customer.

Each `(customer, card)` pair has its own stable Wallet record and `.pkpass` link.

## Registration and operations

The public brand QR now registers the member first. The manager then chooses the appropriate cards. Fast Scan shows every active customer card and its own stamp programs in one screen.

Mistakes remain reversible through an immutable audit flow: the original transaction stays recorded and a compensating reversal restores the exact previous balance.

## Main navigation

```text
استوديو البطاقات
العملاء والبطاقات
السكان السريع
سجل العمليات
الإعدادات
```

## Apple Wallet

Only the platform-owner account can upload the central Apple certificate. A production Pass Type certificate, matching WWDR certificate and a physical iPhone are still required for final live acceptance.

## Verification

```bash
cd backend
PYTHONPATH=. pytest -q

cd ..
PYTHONPATH=backend python scripts/qa_single_brand_studio.py
PYTHONPATH=backend python scripts/qa_card_templates.py
PYTHONPATH=backend python scripts/qa_stamp_experience.py
PYTHONPATH=backend python scripts/qa_public_wallet_join.py
PYTHONPATH=backend python scripts/qa_security_sessions.py
PYTHONPATH=backend python scripts/qa_smoke.py
PYTHONPATH=backend python scripts/qa_legacy_migration.py

cd frontend
npm ci
npm run lint
npm run build
```

## Deployment

Existing installation:

```bash
sudo ./deploy/upgrade.sh
```

The script takes source and PostgreSQL backups, widens Alembic revision storage when needed, rebuilds the services and applies migration `0006_single_brand_studio` without deleting named volumes.

Never run `docker compose down -v` in production.
