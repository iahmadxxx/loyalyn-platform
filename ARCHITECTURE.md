# Loyalyn Architecture

## Product areas

1. Public marketing site
2. Customer enrollment and web membership card
3. Employee QR scanner and customer lookup
4. Brand administration dashboard
5. Wallet certificate vault and pass design editor
6. Loyalty rules engine and transaction ledger
7. Audit, reporting, and fraud controls

## Security boundaries

- Super admins manage platform-wide settings and certificates.
- Brand owners manage only their brands.
- Managers manage assigned branches and employee actions.
- Employees can scan, add eligible transactions, and redeem according to policy.
- Customers can access only their own membership record through signed links or verified sessions.
- Certificate material must be encrypted at rest and never returned by the API.
- Every mutation must include an idempotency key and be written to an audit log.

## Apple Wallet activation workflow

1. Upload `.p12` and password through the owner-only page.
2. Parse PKCS#12 in memory.
3. Validate certificate chain, expiry, and Pass Type ID relationship.
4. Encrypt certificate and password using the platform encryption key.
5. Generate and sign a test pass.
6. Install the test pass manually.
7. Enable production issuance only after successful validation.
8. Notify owners before certificate expiry.

The current repository contains the upload and state workflow. Real certificate persistence is intentionally left behind a clearly marked secure implementation boundary so plaintext credentials cannot be accidentally stored.
