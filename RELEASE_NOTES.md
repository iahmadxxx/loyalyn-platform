# Loyalyn 3.0.0 Release Notes

## Functional repair

- Replaced silent front-end failures with consistent Arabic error messages, busy states and post-save refreshes.
- Added working create, edit, activate/deactivate and detail workflows across brands, branches, customers, staff, loyalty configuration, tiers, rewards, coupons, campaigns and templates.
- Added a searchable customer ledger with safe transaction reversal.

## Loyalty engine

- Points, stamps, hybrid and cashback programs.
- Per-visit/per-spend awards, tier/global/time/branch multipliers, daily cap and point expiry.
- Birthday and referral awards, ready rewards, catalog rewards and coupons.
- Idempotency keys and row locks reduce duplicate/concurrent balance changes.

## Wallet Studio

- Central platform-owner certificate administration.
- Brand-scoped design drafts and publishing.
- Image upload, color/field/barcode customization and live preview.
- Real signed `.pkpass` package generation and Wallet update endpoints.

## Campaigns

- Templates, immediate/scheduled delivery, recurrence and audiences by all customers, birthday, tier, points, inactivity, home branch, ready rewards or a selected customer list.
- In-app, Wallet update, email/SMS/webhook bridges.
- Worker delivery, retries, recipient statuses, clean cancellation of unsent recipients and completed/partial/failed states.

## Security and stability

- Brand isolation, branch-audience isolation and selected-customer validation tests.
- Existing multi-brand account passwords are not replaced when another brand is assigned.
- Per-brand deactivation does not disable access to a different active brand.
- Central Wallet routes are denied to brand managers.
- Audit JSON values are normalized safely.
