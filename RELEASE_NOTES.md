# Loyalyn 5.1.0 Release Notes

## One Wallet card, multiple stamp programs

- Added reusable card templates per brand.
- A single customer card can contain Coffee, Sweet, Breakfast and other independent stamp programs.
- Added Coffee-only, Coffee + Sweet, VIP and any custom card combination through the same editor.
- Existing brands receive a compatible default published template automatically.

## Full card-template management

- Create, edit, reorder, duplicate, publish, unpublish, archive, restore and safe-delete templates.
- Draft edits are isolated from customers until publication.
- Publishing updates the customer-facing representation and active Wallet records.
- Template artwork supports logo, hero, strip and full-background assets.

## Stamp-program lifecycle

- Create and edit arbitrary program labels, targets, rewards, colors and artwork.
- Archive, restore and safely delete unused programs.
- Programs already referenced by historical operations are protected from destructive deletion.
- Template ordering controls the order shown to staff and customers.

## Customer assignment and registration

- Added one active main-card assignment per customer and brand.
- Managers can change a customer's card template without duplicating the account.
- Public registration lets the customer choose from published cards enabled for public join.
- Stable membership QR and Apple Wallet readiness remain separate and explicit.

## Fast Scan and reversal

- Fast Scan displays only programs included in the customer's assigned card.
- Added auditable reversal of an accidental stamp/redeem operation.
- Reversal restores exact prior values, retains the original record and creates a compensating transaction.
- Duplicate, unauthorized and cross-template operations are blocked server-side.

## Compatibility and migrations

- Added Alembic revision `0004_card_templates`.
- Migration is idempotent for old bootstrapped schemas and normal PostgreSQL upgrades.
- Existing customers, balances, brand profiles, Wallet designs, employees, permissions and audit history are preserved.
- The deployment preflight retains the Alembic revision-column widening fix.

## Frontend and mobile

- Added a dedicated Cards section and a separate Stamp Programs section.
- Updated Wallet Studio to preview and issue published templates.
- Updated public join and customer card pages for multi-program cards.
- Added responsive template editors, ordered program picker, operation history and mobile quick navigation.

## 5.1.0 — Advanced card and stamp studio

- Added a full stamp icon library covering coffee, drinks, desserts, food and general symbols.
- Added custom empty/filled stamp images with replace and delete controls.
- Added stamp display modes: icons + count, icons only, count only and progress bar.
- Added circle, rounded, square, diamond and frameless stamp shapes.
- Added per-program operational controls: multiple stamps, maximum per action, daily customer limit, active dates and carry-over.
- Added stamp program duplication and reordering.
- Expanded card design presets, gradients, image fit/position, corner styles, QR/member/reward visibility and front-program count.
- Added safe image removal for card logos, hero images, backgrounds and Apple strip images.
- Fast Scan now exposes +1, +2 and +3 buttons only when permitted by the selected program.
- Added migration `0005_stamp_customization`; existing cards, programs and customer history are preserved.
