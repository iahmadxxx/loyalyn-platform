"""Advanced stamp customization settings.

Revision ID: 0005_stamp_customization
Revises: 0004_card_templates
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_stamp_customization"
down_revision = "0004_card_templates"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = _columns("stamp_programs")
    if "settings" not in columns:
        with op.batch_alter_table("stamp_programs") as batch:
            batch.add_column(sa.Column("settings", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))


def downgrade() -> None:
    if "settings" in _columns("stamp_programs"):
        with op.batch_alter_table("stamp_programs") as batch:
            batch.drop_column("settings")
