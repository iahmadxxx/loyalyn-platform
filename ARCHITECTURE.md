# Loyalyn 3 Architecture

## Trust boundaries

- `platform_owner`: platform-wide brand administration and central Apple Wallet credential only.
- `brand_admin`: full control inside authorized brand memberships; no central credential access.
- `manager`: operational brand access without platform or employee-account administration.
- `employee`: customer, loyalty application, reward redemption and Wallet issuing as allowed.

Every brand-scoped API calls `brand_access()` on the server. Hiding a navigation item is not treated as authorization.

## Data flow

```text
Next.js dashboard
  -> FastAPI authorization + validation
  -> PostgreSQL transaction / audit log
  -> response with explicit success or error

Campaign API
  -> notification_campaigns
  -> worker claim with row lock
  -> recipients + channel provider
  -> delivery counters / retries

Brand Wallet design
  + customer balance
  + central platform certificate
  -> signed pkpass
  -> Apple Wallet web service / APNs update
```

## Main tables

- Identity/tenancy: `users`, `brands`, `user_brand_access`, `branches`, `employees`
- Customers/loyalty: `customers` (including optional `home_branch_id`), `loyalty_programs`, `loyalty_transactions`, `membership_tiers`, `rewards`, `coupons`, `coupon_redemptions`
- Wallet: `brand_wallet_designs`, `platform_wallet_credentials`, `wallet_passes`, `wallet_devices`, `wallet_registrations`
- Messaging: `notification_templates`, `notification_campaigns`, `notification_recipients`, `notifications`
- Accountability: `audit_logs`

## Sensitive data

- `.env` is not included in the release archive.
- Wallet files live under the `loyalyn_data` Docker volume.
- Wallet credential folders and extracted private keys are restricted to owner-only filesystem permissions.
- Certificate passwords are encrypted before database storage and are never returned by the API.
