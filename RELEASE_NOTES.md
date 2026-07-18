# Loyalyn 6.0.1 Release Notes

## Focused single-brand interface

- Replaced the broad multi-brand control interface with a focused stamp-card studio for the brand attached to the account.
- Reduced the primary navigation to Studio, Customers, Fast Scan, Operations and Settings.
- Preserved historical database records and server-side tenant/permission protections for safe upgrades.

## One-screen card production

- Card list, live preview, design fields, images, stamp programs and publish controls now live in one workspace.
- Added undo/redo for unsaved card edits.
- Added independent card duplication, publishing and archiving.
- Any number of Coffee-only, Sweet-only, Coffee + Sweet or custom cards can remain published together.

## Exact stamp customization

- Added `display_options` to every stamp program.
- Added filled and empty stamp artwork uploads.
- Added icon library, size, gap, X/Y offset, contain/cover and slot-shape controls.
- Added a deterministic server-side Wallet strip renderer at 1x and 2x sizes.
- Oversized or non-square artwork is contained inside fixed stamp slots instead of changing the row position.

## Several cards per customer

- Replaced the one-card-per-customer constraint with a unique `(customer, card template)` assignment.
- A customer can have no card, one card or several active cards.
- Added attach, detach, replace-list and list-assignment APIs.
- Added one distinct Wallet pass per `(customer, card template)` pair.
- Customer dialog can issue/open a card and copy its share link.

## Registration flow

- The simplified public page registers the customer first without forcing a card selection.
- The manager chooses the card or cards afterward and sends the corresponding Wallet links.
- Legacy clients that explicitly request a card retain the direct self-service issue path.

## Migration

- Added Alembic revision `0006_single_brand_studio`.
- Existing customers, stamps, transactions, Wallet credentials and old card assignments are preserved.
- The migration removes the historical single-customer-card uniqueness and adds compound assignment/pass constraints.

## 6.0.1 migration-chain hotfix

- Restores the previously deployed `0005_stamp_customization` Alembic revision.
- Moves the single-brand studio migration to `0006_single_brand_studio` and chains it after `0005_stamp_customization`.
- Prevents API restart loops when upgrading an existing v5.1 database.
- Deployment now runs Alembic as an explicit pre-start step so migration errors are visible before API startup.
