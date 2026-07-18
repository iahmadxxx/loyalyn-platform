# Loyalyn 4.1.0

Loyalyn is a multi-brand loyalty operating system built with FastAPI, PostgreSQL, Next.js and Docker Compose. Version 4.1 preserves the full V4 feature set and adds a hardened browser session model, reliable permission-aware screens, branch-scoped employee operations and a fully responsive Arabic mobile interface.

## One platform, different brand programs

The platform owner chooses the appropriate profile for every brand:

- **Stamps only**: multiple independent stamp cards, fast scan, rewards, Wallet and campaigns.
- **Points only**: points, tiers, catalog rewards, coupons, Wallet and campaigns.
- **Stamps + points**: both systems together.
- **Full loyalty**: stamps, points, cashback, tiers, rewards, coupons, Wallet and campaigns.
- **Custom**: individual feature switches.

Changing a profile never deletes customers, balances, cards, rewards or transaction history. Disabled features are hidden in the interface and rejected by the API until re-enabled.

## Stamp-first experience

- Create Coffee, Sweet, Breakfast or any other independent stamp card inside one brand.
- Set each card's target, reward, colors, icon, full artwork and empty/filled stamp images.
- Scan a membership QR, select the purchased product card and add one stamp in a few taps.
- Redeem one card's reward without affecting another card.
- Use idempotency keys and an auditable transaction ledger to prevent duplicate operations.

## Reliable mobile administration

- Fixed mobile header with quick access to the scan screen.
- Slide-out navigation, touch targets of at least 44px and form fields sized for iPhone and Android keyboards.
- Single-column responsive forms, mobile bottom-sheet dialogs and horizontally safe tables.
- Wallet Studio, customer management, stamp cards and employee scan have dedicated mobile layouts.
- A section-level error boundary prevents one screen from crashing the whole administration app.

## Employee permissions and privacy

- Every user receives effective permissions from the role defaults plus explicit per-brand overrides; unchecked permissions are stored as explicit revocations.
- A branch-scoped employee is forced to the assigned branch by the backend.
- Employees search customers by phone, name or membership code instead of downloading the full customer list by default.
- Privacy-limited employee search omits email, birthday, notes, tags and total spending unless broader permissions are granted.
- Navigation and action buttons follow effective permissions, while the API independently enforces every sensitive operation and prevents delegated managers from granting permissions they do not possess.

## Secure browser sessions

- Short-lived access tokens and rotating refresh tokens.
- Access and refresh tokens are stored in Secure HttpOnly cookies, not `localStorage`.
- CSRF validation for unsafe cookie-authenticated requests.
- Server-side session records allow logout and revocation to invalidate captured access tokens.
- Security headers include HSTS in production, CSP, frame denial, content-type protection, referrer policy and a restricted permissions policy.

Existing users will be asked to sign in once after upgrading from the previous localStorage-based session.

## Apple Wallet ownership model

Only the platform owner can upload and manage the central Apple Wallet credential. Brand managers can design, publish and issue cards but cannot view, download or replace the certificate or password. New brands use the active central signer automatically.

Apple Wallet limits free-form layout. Loyalyn supports the safe fields Apple permits: colors, logos, hero/strip/background artwork, visible fields, barcode and program data, with a live responsive preview.

## Local verification

```bash
PYTHONPATH=backend pytest -q backend/tests
PYTHONPATH=backend python scripts/qa_smoke.py
PYTHONPATH=backend python scripts/qa_stamp_experience.py
PYTHONPATH=backend python scripts/qa_legacy_migration.py
PYTHONPATH=backend python scripts/qa_security_sessions.py

cd frontend
npm ci
npm run lint
NEXT_PUBLIC_API_URL=https://api.loyalyn.site npm run build
```

The Python QA scripts use isolated SQLite databases under `/tmp` and never touch production data.

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

The upgrade script creates source and PostgreSQL backups before rebuilding. Never run `docker compose down -v` in production because it deletes named volumes.
