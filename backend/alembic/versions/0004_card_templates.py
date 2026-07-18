"""Card templates, template programs, customer assignment and stamp reversals.

Revision ID: 0004_card_templates
Revises: 0003_security_sessions
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_card_templates"
down_revision = "0003_security_sessions"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name) if index.get("name")}


def _foreign_keys(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {fk["name"] for fk in inspector.get_foreign_keys(table_name) if fk.get("name")}


def _create_index_if_missing(name: str, table: str, columns: list[str]) -> None:
    if name not in _indexes(table):
        op.create_index(name, table, columns)


def upgrade() -> None:
    tables = _table_names()

    # Migration 0001 intentionally uses the current SQLAlchemy metadata so it can
    # bootstrap very old installations. In a clean test database that may mean
    # future tables already exist by the time this revision runs. Every operation
    # below is therefore idempotent while still performing a normal 0003 -> 0004
    # production upgrade.
    if "card_templates" not in tables:
        op.create_table(
            "card_templates",
            sa.Column("brand_id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(160), nullable=False),
            sa.Column("name_en", sa.String(160), nullable=True),
            sa.Column("slug", sa.String(80), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("allow_public_join", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("background_color", sa.String(7), nullable=False, server_default="#111827"),
            sa.Column("foreground_color", sa.String(7), nullable=False, server_default="#FFFFFF"),
            sa.Column("label_color", sa.String(7), nullable=False, server_default="#C6FF4A"),
            sa.Column("logo_text", sa.String(120), nullable=False, server_default="LOYALYN"),
            sa.Column("card_title", sa.String(120), nullable=False, server_default="بطاقة الولاء"),
            sa.Column("logo_url", sa.Text(), nullable=True),
            sa.Column("hero_url", sa.Text(), nullable=True),
            sa.Column("background_image_url", sa.Text(), nullable=True),
            sa.Column("strip_url", sa.Text(), nullable=True),
            sa.Column("layout_style", sa.String(30), nullable=False, server_default="classic"),
            sa.Column("overlay_opacity", sa.Integer(), nullable=False, server_default="25"),
            sa.Column("barcode_format", sa.String(40), nullable=False, server_default="PKBarcodeFormatQR"),
            sa.Column("fields", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("terms", sa.Text(), nullable=True),
            sa.Column("draft_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("published_version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("published_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("brand_id", "slug", name="uq_card_template_brand_slug"),
        )
    _create_index_if_missing("ix_card_templates_brand_id", "card_templates", ["brand_id"])
    _create_index_if_missing("ix_card_templates_status", "card_templates", ["status"])
    _create_index_if_missing("ix_card_templates_is_default", "card_templates", ["is_default"])

    tables = _table_names()
    if "card_template_programs" not in tables:
        op.create_table(
            "card_template_programs",
            sa.Column("card_template_id", sa.Uuid(), nullable=False),
            sa.Column("stamp_program_id", sa.Uuid(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["card_template_id"], ["card_templates.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["stamp_program_id"], ["stamp_programs.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("card_template_id", "stamp_program_id", name="uq_card_template_program"),
        )
    _create_index_if_missing("ix_card_template_programs_card_template_id", "card_template_programs", ["card_template_id"])
    _create_index_if_missing("ix_card_template_programs_stamp_program_id", "card_template_programs", ["stamp_program_id"])

    tables = _table_names()
    if "customer_card_assignments" not in tables:
        op.create_table(
            "customer_card_assignments",
            sa.Column("brand_id", sa.Uuid(), nullable=False),
            sa.Column("customer_id", sa.Uuid(), nullable=False),
            sa.Column("card_template_id", sa.Uuid(), nullable=False),
            sa.Column("assigned_by_actor_id", sa.Uuid(), nullable=True),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["card_template_id"], ["card_templates.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["assigned_by_actor_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("customer_id"),
        )
    _create_index_if_missing("ix_customer_card_assignments_brand_id", "customer_card_assignments", ["brand_id"])
    _create_index_if_missing("ix_customer_card_assignments_customer_id", "customer_card_assignments", ["customer_id"])
    _create_index_if_missing("ix_customer_card_assignments_card_template_id", "customer_card_assignments", ["card_template_id"])

    stamp_program_columns = _columns("stamp_programs")
    if "is_archived" not in stamp_program_columns or "archived_at" not in stamp_program_columns:
        with op.batch_alter_table("stamp_programs") as batch:
            if "is_archived" not in stamp_program_columns:
                batch.add_column(sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()))
            if "archived_at" not in stamp_program_columns:
                batch.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    _create_index_if_missing("ix_stamp_programs_is_archived", "stamp_programs", ["is_archived"])

    tx_columns = _columns("stamp_transactions")
    tx_fks = _foreign_keys("stamp_transactions")
    missing_tx_columns = {
        "original_transaction_id",
        "reversal_transaction_id",
        "reversed_at",
        "reversed_by_actor_id",
        "reversal_reason",
    } - tx_columns
    missing_tx_fks = {
        "fk_stamp_tx_original",
        "fk_stamp_tx_reversal",
        "fk_stamp_tx_reversed_by",
    } - tx_fks
    if missing_tx_columns or missing_tx_fks:
        with op.batch_alter_table("stamp_transactions") as batch:
            if "original_transaction_id" in missing_tx_columns:
                batch.add_column(sa.Column("original_transaction_id", sa.Uuid(), nullable=True))
            if "reversal_transaction_id" in missing_tx_columns:
                batch.add_column(sa.Column("reversal_transaction_id", sa.Uuid(), nullable=True))
            if "reversed_at" in missing_tx_columns:
                batch.add_column(sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True))
            if "reversed_by_actor_id" in missing_tx_columns:
                batch.add_column(sa.Column("reversed_by_actor_id", sa.Uuid(), nullable=True))
            if "reversal_reason" in missing_tx_columns:
                batch.add_column(sa.Column("reversal_reason", sa.Text(), nullable=True))
            if "fk_stamp_tx_original" in missing_tx_fks:
                batch.create_foreign_key("fk_stamp_tx_original", "stamp_transactions", ["original_transaction_id"], ["id"], ondelete="SET NULL")
            if "fk_stamp_tx_reversal" in missing_tx_fks:
                batch.create_foreign_key("fk_stamp_tx_reversal", "stamp_transactions", ["reversal_transaction_id"], ["id"], ondelete="SET NULL")
            if "fk_stamp_tx_reversed_by" in missing_tx_fks:
                batch.create_foreign_key("fk_stamp_tx_reversed_by", "users", ["reversed_by_actor_id"], ["id"], ondelete="SET NULL")
    _create_index_if_missing("ix_stamp_transactions_original_transaction_id", "stamp_transactions", ["original_transaction_id"])
    _create_index_if_missing("ix_stamp_transactions_reversal_transaction_id", "stamp_transactions", ["reversal_transaction_id"])
    _create_index_if_missing("ix_stamp_transactions_reversed_at", "stamp_transactions", ["reversed_at"])

    wallet_columns = _columns("wallet_passes")
    wallet_fks = _foreign_keys("wallet_passes")
    if "card_template_id" not in wallet_columns or "fk_wallet_pass_template" not in wallet_fks:
        with op.batch_alter_table("wallet_passes") as batch:
            if "card_template_id" not in wallet_columns:
                batch.add_column(sa.Column("card_template_id", sa.Uuid(), nullable=True))
            if "fk_wallet_pass_template" not in wallet_fks:
                batch.create_foreign_key("fk_wallet_pass_template", "card_templates", ["card_template_id"], ["id"], ondelete="SET NULL")
    _create_index_if_missing("ix_wallet_passes_card_template_id", "wallet_passes", ["card_template_id"])


def downgrade() -> None:
    op.drop_index("ix_wallet_passes_card_template_id", table_name="wallet_passes")
    with op.batch_alter_table("wallet_passes") as batch:
        batch.drop_constraint("fk_wallet_pass_template", type_="foreignkey")
        batch.drop_column("card_template_id")
    op.drop_index("ix_stamp_transactions_reversed_at", table_name="stamp_transactions")
    op.drop_index("ix_stamp_transactions_reversal_transaction_id", table_name="stamp_transactions")
    op.drop_index("ix_stamp_transactions_original_transaction_id", table_name="stamp_transactions")
    with op.batch_alter_table("stamp_transactions") as batch:
        batch.drop_constraint("fk_stamp_tx_reversed_by", type_="foreignkey")
        batch.drop_constraint("fk_stamp_tx_reversal", type_="foreignkey")
        batch.drop_constraint("fk_stamp_tx_original", type_="foreignkey")
        batch.drop_column("reversal_reason")
        batch.drop_column("reversed_by_actor_id")
        batch.drop_column("reversed_at")
        batch.drop_column("reversal_transaction_id")
        batch.drop_column("original_transaction_id")
    op.drop_index("ix_stamp_programs_is_archived", table_name="stamp_programs")
    with op.batch_alter_table("stamp_programs") as batch:
        batch.drop_column("archived_at")
        batch.drop_column("is_archived")
    op.drop_table("customer_card_assignments")
    op.drop_table("card_template_programs")
    op.drop_table("card_templates")
