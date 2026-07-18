"""Single-brand card studio, exact stamp layout and multi-card customers.

Revision ID: 0006_single_brand_studio
Revises: 0005_stamp_customization
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_single_brand_studio"
down_revision = "0005_stamp_customization"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {row["name"] for row in inspector.get_columns(table)}


def _unique_constraints(table: str) -> dict[str, list[str]]:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return {}
    return {
        row["name"]: list(row.get("column_names") or [])
        for row in inspector.get_unique_constraints(table)
        if row.get("name")
    }


def _indexes(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {row["name"] for row in inspector.get_indexes(table) if row.get("name")}


def upgrade() -> None:
    if "stamp_programs" in _tables() and "display_options" not in _columns("stamp_programs"):
        with op.batch_alter_table("stamp_programs") as batch:
            batch.add_column(sa.Column("display_options", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))

    if "customer_card_assignments" in _tables():
        columns = _columns("customer_card_assignments")
        uniques = _unique_constraints("customer_card_assignments")
        with op.batch_alter_table("customer_card_assignments") as batch:
            if "is_active" not in columns:
                batch.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
            for name, column_names in uniques.items():
                if column_names == ["customer_id"]:
                    batch.drop_constraint(name, type_="unique")
            if "uq_customer_card_template" not in uniques:
                batch.create_unique_constraint("uq_customer_card_template", ["customer_id", "card_template_id"])
        if "ix_customer_card_assignments_is_active" not in _indexes("customer_card_assignments"):
            op.create_index("ix_customer_card_assignments_is_active", "customer_card_assignments", ["is_active"])

    if "wallet_passes" in _tables():
        uniques = _unique_constraints("wallet_passes")
        with op.batch_alter_table("wallet_passes") as batch:
            for name, column_names in uniques.items():
                if column_names in (["brand_id", "customer_id"], ["customer_id"]):
                    batch.drop_constraint(name, type_="unique")
            if "uq_wallet_pass_customer_template" not in uniques:
                batch.create_unique_constraint("uq_wallet_pass_customer_template", ["customer_id", "card_template_id"])


def downgrade() -> None:
    # Multi-card data cannot be losslessly collapsed to a single card per customer.
    # Downgrade keeps rows and only removes the presentation-only column.
    if "stamp_programs" in _tables() and "display_options" in _columns("stamp_programs"):
        with op.batch_alter_table("stamp_programs") as batch:
            batch.drop_column("display_options")
