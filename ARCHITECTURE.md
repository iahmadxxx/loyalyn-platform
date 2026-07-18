# Loyalyn 4.1 Architecture

## One tenant-isolated platform

Each brand stores a `program_mode` and optional `feature_flags`. The resolved capability set controls navigation and API feature gates without deleting disabled-feature data.

```text
Platform
  ├─ Brand A: Stamps only
  ├─ Brand B: Points only
  ├─ Brand C: Stamps + points
  └─ Brand D: Full or Custom
```

## Trust boundaries

- `platform_owner`: platform-wide administration and central Apple Wallet credential.
- `brand_admin`: full control inside authorized brands; no central credential access.
- `manager`: operational/configuration access granted by effective permissions.
- `employee`: branch-scoped customer search, registration, scan, loyalty issue and reward redemption as allowed.

Every brand-scoped API performs server-side brand access, feature and action-permission checks. Navigation visibility is a usability layer, never the authorization boundary.

## Browser authentication

```text
Login
  -> short access JWT in Secure HttpOnly cookie
  -> opaque rotating refresh token in Secure HttpOnly cookie
  -> AuthSession row (hashed refresh token, expiry, revocation)
  -> CSRF cookie/header for unsafe cross-subdomain requests
```

Logging out revokes the AuthSession, so an access JWT captured before logout is rejected even before its short expiry.

## Reliable frontend data flow

```text
Dashboard metrics.branch_count  (number)
Branch options[]                 (array, independent state)

Tab/brand change
  -> clear stale tab payload
  -> load required data
  -> normalize lists with safeArray
  -> settle optional requests independently
  -> render inside SectionErrorBoundary
```

This prevents the historical `number.map()` / `number.filter()` client crash and keeps one denied optional endpoint from taking down the app.

## Employee operational flow

```text
Employee brand access + assigned branch
  -> /branch-options returns permitted branch only
  -> customer search requires a query unless customers.list is granted
  -> privacy-limited customer summary
  -> selected scan/add/redeem operation
  -> operational_branch enforces branch server-side
  -> transaction + audit + Wallet update
```

## Main tables

- Identity/tenancy: `users`, `auth_sessions`, `brands`, `user_brand_access`, `branches`, `employees`
- General loyalty: `customers`, `loyalty_programs`, `loyalty_transactions`, `membership_tiers`, `rewards`, `coupons`, `coupon_redemptions`
- Stamp experience: `stamp_programs`, `customer_stamp_cards`, `stamp_transactions`
- Wallet: `brand_wallet_designs`, `platform_wallet_credentials`, `wallet_passes`, `wallet_devices`, `wallet_registrations`
- Messaging: `notification_templates`, `notification_campaigns`, `notification_recipients`, `notifications`
- Accountability: `audit_logs`

## Sensitive data

- `.env`, certificates and generated secrets are excluded from release archives.
- Wallet files live under the protected Docker data volume.
- Certificate passwords are encrypted and never returned by the API.
- Brand managers never receive or download the central Apple certificate.
- Browser bearer credentials are unavailable to JavaScript because they are HttpOnly.
