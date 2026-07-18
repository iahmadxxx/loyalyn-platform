"""Loyalyn v3 production foundation

Revision ID: 0001_loyalyn_v3
Revises:
"""
from alembic import op
import sqlalchemy as sa
import uuid
from datetime import datetime, timezone
from sqlalchemy import inspect, select, text
from app.models import Base

revision = "0001_loyalyn_v3"
down_revision = None
branch_labels = None
depends_on = None


def _add_missing_columns(bind, table_name, columns):
    inspector = inspect(bind)
    if table_name not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns(table_name)}
    for column in columns:
        if column.name not in existing:
            op.add_column(table_name, column)




def _new_id(bind):
    value = uuid.uuid4()
    return value.hex if bind.dialect.name == "sqlite" else value


def _insert_missing_foundation_rows(bind):
    """Backfill tenant/access defaults for brands created by the legacy MVP."""
    # Reflect the database after adding the v3 columns. Using the current
    # application metadata here would select future-version columns that do
    # not exist yet on a legacy database (for example program_mode).
    metadata = sa.MetaData()
    metadata.reflect(bind=bind)
    tables = metadata.tables
    brands = tables["brands"]
    users = tables["users"]
    access = tables["user_brand_access"]
    employees = tables["employees"]
    programs = tables["loyalty_programs"]
    designs = tables["brand_wallet_designs"]
    tiers = tables["membership_tiers"]
    now = datetime.now(timezone.utc)

    brand_ids = [row[0] for row in bind.execute(select(brands.c.id)).all()]
    for brand_id in brand_ids:
        brand = bind.execute(select(brands).where(brands.c.id == brand_id)).mappings().first()
        if not bind.execute(select(programs.c.id).where(programs.c.brand_id == brand_id)).first():
            bind.execute(programs.insert().values(
                id=_new_id(bind), brand_id=brand_id, enabled=True, program_type="hybrid",
                points_per_visit=10, points_per_currency=1, required_stamps=6,
                stamp_reward_title="مكافأة مجانية", reward_points=100,
                reward_title="مكافأة مجانية", birthday_bonus=0, referral_bonus=0,
                cashback_percent=0, allow_manual_adjustment=True, rules={},
                created_at=now, updated_at=now,
            ))
        if not bind.execute(select(designs.c.id).where(designs.c.brand_id == brand_id)).first():
            bind.execute(designs.insert().values(
                id=_new_id(bind), brand_id=brand_id,
                background_color=(brand or {}).get("primary_color") or "#111827",
                foreground_color="#FFFFFF",
                label_color=(brand or {}).get("accent_color") or "#C6FF4A",
                logo_text=(brand or {}).get("name") or "LOYALYN",
                card_title="بطاقة الولاء", layout_style="classic", overlay_opacity=25,
                barcode_format="PKBarcodeFormatQR",
                fields={"show_points": True, "show_stamps": True, "show_rewards": True, "show_tier": True, "show_visits": True},
                draft_version=1, published_version=0, is_published=False,
                created_at=now, updated_at=now,
            ))
        if not bind.execute(select(tiers.c.id).where(tiers.c.brand_id == brand_id)).first():
            defaults = [
                ("برونزي", 0, "#B7791F", 0),
                ("فضي", 1, "#A0AEC0", 500),
                ("ذهبي", 2, "#D69E2E", 1500),
                ("VIP", 3, "#C6FF4A", 5000),
            ]
            for name, rank, color, min_points in defaults:
                bind.execute(tiers.insert().values(
                    id=_new_id(bind), brand_id=brand_id, name=name, rank=rank,
                    color=color, min_points=min_points, min_spend=0,
                    points_multiplier=1, benefits={}, is_active=True,
                    created_at=now, updated_at=now,
                ))

    legacy_users = bind.execute(
        select(users.c.id, users.c.brand_id, users.c.email, users.c.full_name, users.c.role, users.c.is_active)
        .where(users.c.brand_id.is_not(None))
    ).mappings().all()
    for row in legacy_users:
        existing = bind.execute(
            select(access.c.id).where(access.c.user_id == row["id"], access.c.brand_id == row["brand_id"])
        ).first()
        normalized_role = "brand_admin" if row["role"] in {"owner", "admin", "manager", "brand_admin"} else row["role"]
        if not existing:
            bind.execute(access.insert().values(
                id=_new_id(bind), user_id=row["id"], brand_id=row["brand_id"],
                role=normalized_role, permissions={}, is_active=bool(row["is_active"]),
                created_at=now, updated_at=now,
            ))
        employee_exists = bind.execute(
            select(employees.c.id).where(employees.c.brand_id == row["brand_id"], employees.c.email == row["email"])
        ).first()
        if not employee_exists:
            bind.execute(employees.insert().values(
                id=_new_id(bind), brand_id=row["brand_id"], user_id=row["id"],
                name=row["full_name"], email=row["email"], role=normalized_role,
                permissions={}, is_active=bool(row["is_active"]),
                created_at=now, updated_at=now,
            ))


def upgrade():
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)
    _add_missing_columns(bind, "users", [sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True)])
    _add_missing_columns(bind, "brands", [
        sa.Column("currency", sa.String(8), nullable=False, server_default="QAR"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Qatar"),
        sa.Column("locale", sa.String(12), nullable=False, server_default="ar"),
    ])
    _add_missing_columns(bind, "branches", [
        sa.Column("phone", sa.String(32), nullable=True), sa.Column("manager_name", sa.String(120), nullable=True),
        sa.Column("latitude", sa.String(32), nullable=True), sa.Column("longitude", sa.String(32), nullable=True),
    ])
    _add_missing_columns(bind, "employees", [sa.Column("user_id", sa.Uuid(), nullable=True)])
    _add_missing_columns(bind, "customers", [
        sa.Column("home_branch_id", sa.Uuid(), nullable=True),
        sa.Column("birthday", sa.Date(), nullable=True), sa.Column("total_spend", sa.Numeric(12,2), nullable=False, server_default="0"),
        sa.Column("last_visit_at", sa.DateTime(timezone=True), nullable=True), sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text(), nullable=True),
    ])
    _add_missing_columns(bind, "loyalty_programs", [
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("points_per_currency", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("stamp_reward_title", sa.String(160), nullable=False, server_default="مكافأة مجانية"),
        sa.Column("birthday_bonus", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("referral_bonus", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cashback_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("points_expiry_days", sa.Integer(), nullable=True),
        sa.Column("daily_points_cap", sa.Integer(), nullable=True),
        sa.Column("allow_manual_adjustment", sa.Boolean(), nullable=False, server_default=sa.true()),
    ])
    _add_missing_columns(bind, "loyalty_transactions", [
        sa.Column("points_before", sa.Integer(), nullable=False, server_default="0"), sa.Column("points_after", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stamps_before", sa.Integer(), nullable=False, server_default="0"), sa.Column("stamps_after", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(12,2), nullable=False, server_default="0"), sa.Column("reference", sa.String(120), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remaining_points", sa.Integer(), nullable=False, server_default="0"),
    ])
    _add_missing_columns(bind, "wallet_passes", [
        sa.Column("authentication_token", sa.String(100), nullable=True), sa.Column("pass_type_identifier", sa.String(180), nullable=True),
        sa.Column("update_tag", sa.Integer(), nullable=False, server_default="1"), sa.Column("last_push_at", sa.DateTime(timezone=True), nullable=True),
    ])
    _add_missing_columns(bind, "notification_campaigns", [
        sa.Column("recurrence", sa.String(20), nullable=False, server_default="none"),
        sa.Column("series_key", sa.String(80), nullable=True),
    ])
    _add_missing_columns(bind, "notifications", [sa.Column("campaign_id", sa.Uuid(), nullable=True)])
    bind.execute(text("UPDATE users SET role='platform_owner' WHERE role IN ('owner','admin') AND brand_id IS NULL"))
    bind.execute(text("UPDATE users SET role='brand_admin' WHERE role IN ('owner','admin','manager') AND brand_id IS NOT NULL"))
    _insert_missing_foundation_rows(bind)


def downgrade():
    pass
