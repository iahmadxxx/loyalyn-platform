# Loyalyn 6.0 Architecture

## Product surface

V6 presents a single-brand stamp-card product even though the historical tenant-safe backend remains intact for upgrade compatibility.

```text
Brand account
  ├─ Card Studio
  │   ├─ Coffee card
  │   ├─ Sweet card
  │   └─ Coffee + Sweet card
  ├─ Customers + card assignment
  ├─ Fast Scan
  ├─ Operation/reversal history
  └─ Wallet certificate/settings
```

## Card and stamp records

- `card_templates`: independent draft/published cards and design settings;
- `card_template_programs`: ordered stamp programs inside each card;
- `stamp_programs`: targets, rewards, images and exact display options;
- `customer_card_assignments`: active `(customer, card)` links;
- `customer_stamp_cards`: balances per customer/program;
- `wallet_passes`: one pass per `(customer, card)`;
- `stamp_transactions`: immutable add/redeem/reversal history.

## Wallet rendering

Apple controls the Store Card field layout. Loyalyn therefore converts the stamp area to a deterministic dynamic strip:

```text
program balances + display options + uploaded art
  -> fixed slot geometry
  -> contain/cover + pixel offsets inside each slot
  -> strip.png 375×123
  -> strip@2x.png 750×246
  -> signed .pkpass
```

The renderer limits front-strip density and keeps complete program details in pass fields/back information.

## Assignment model

A customer may have zero, one or several active card assignments. Attaching or detaching one card synchronizes only the programs needed by the active set. Detaching a card revokes that card's Wallet pass without revoking other active passes.

## Trust boundaries

- `platform_owner`: central Apple credential and platform-sensitive settings;
- brand managers: card/program/customer/operation controls only within authorized brands;
- employees: permission and branch-scoped scan operations.

The simplified navigation is not the security boundary. Every API still enforces tenant, feature, role and operation permissions server-side.

## Browser security

- short access JWT in Secure HttpOnly cookie;
- rotating opaque refresh token tied to an `AuthSession` row;
- CSRF cookie/header validation for unsafe browser requests;
- logout/session revocation;
- CSP and standard browser security headers.

## Upgrade safety

Migration `0005_single_brand_studio` adds display options and active assignments, removes the old one-card uniqueness and creates compound uniqueness for customer-card assignments and Wallet passes. Historical records and named Docker volumes are retained.
