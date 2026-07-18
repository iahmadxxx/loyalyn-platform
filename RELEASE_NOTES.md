# Loyalyn 4.1.0 Release Notes

## Critical frontend reliability fix

- Separated dashboard branch counts from branch option arrays.
- Normalized every list response before `.map()` or `.filter()`.
- Cleared stale section state when switching tabs or brands.
- Used settled loading for optional requests so one denied/nonessential endpoint does not crash a whole page.
- Added a section error boundary with an Arabic retry action instead of a full black application screen.

## Mobile redesign

- Added a fixed compact mobile header, slide-out RTL menu and quick Fast Scan button.
- Reflowed grids, forms, customer cards, Wallet Studio and stamp tools for phone widths.
- Added mobile bottom-sheet dialogs, safe table overflow, 44px touch targets and 16px form controls.
- Prevented horizontal overflow on tested 390×844 mobile screens.

## Permission-aware employee experience

- Added effective permissions to `/api/auth/me` and per-brand access data.
- Added explicit employee/manager permission presets and a manager-facing permission editor that stores both grants and revocations.
- Default cashier navigation now focuses on Overview, Customer Search and Fast Scan.
- Added a branch-options endpoint that returns only the employee's permitted branch.
- Forced employee operations to the assigned branch on the backend.
- Replaced full customer downloads with privacy-limited two-character server search for employees without `customers.list`.
- Separated customer registration, editing, history, ordinary loyalty actions, manual balance adjustment, reward redemption and Wallet issue permissions so only valid buttons appear.
- Prevented delegated users from granting permissions above their own and revoke active sessions after an employee password change.
- Added minimal reward/coupon option endpoints for operational redemption without exposing configuration screens.

## Secure browser authentication

- Replaced seven-day `localStorage` JWT usage with short-lived access cookies and rotating refresh cookies.
- Added server-side `auth_sessions` records and migration `0003_security_sessions`.
- Added refresh replay prevention, server-side logout revocation and CSRF validation.
- Added production HSTS, CSP, frame denial, content-type, referrer and permissions-policy headers.

## V4 features preserved

- Per-brand Stamps only, Points only, Stamps + points, Full and Custom profiles.
- Independent Coffee/Sweet/product stamp cards, public join QR and Fast Scan.
- Points, cashback, tiers, rewards, coupons and campaigns when enabled.
- Wallet Studio and platform-owner-only central Apple credential.
- Feature switches continue to preserve disabled-feature data.

## Deployment robustness

- Health checks now retry connection-refused and transient startup errors for both API and frontend.
- The public npm registry remains pinned and no internal artifact URL is present.
