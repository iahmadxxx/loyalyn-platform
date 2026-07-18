"""Program profiles, multi stamp cards, public join and advanced Wallet design.

Revision ID: 0002_program_profiles_stamp_experience
Revises: 0001_loyalyn_v3
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, select, text

from app.models import Base

revision = "0002_program_profiles_stamp_experience"
down_revision = "0001_loyalyn_v3"
branch_labels = None
depends_on = None


def _add_missing_columns(bind, table_name: str, columns: list[sa.Column]) -> None:
    inspector = inspect(bind)
    if table_name not in inspector.get_table_names():
        return
    existing = {item["name"] for item in inspector.get_columns(table_name)}
    for column in columns:
        if column.name not in existing:
            op.add_column(table_name, column)


def _slug(value: str, fallback: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return value[:64] or fallback


def upgrade() -> None:
    bind = op.get_bind()
    # Current metadata uses checkfirst so fresh installs and upgrades share one path.
    Base.metadata.create_all(bind=bind, checkfirst=True)

    _add_missing_columns(bind, "brands", [
        sa.Column("program_mode", sa.String(30), nullable=False, server_default="full"),
        sa.Column("feature_flags", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("join_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("join_require_email", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("join_welcome_text", sa.Text(), nullable=True),
    ])
    _add_missing_columns(bind, "stamp_programs", [
        sa.Column("slug", sa.String(80), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reward_type", sa.String(30), nullable=False, server_default="free_item"),
        sa.Column("background_color", sa.String(7), nullable=False, server_default="#111827"),
        sa.Column("accent_color", sa.String(7), nullable=False, server_default="#C6FF4A"),
        sa.Column("card_image_url", sa.Text(), nullable=True),
        sa.Column("empty_stamp_image_url", sa.Text(), nullable=True),
        sa.Column("filled_stamp_image_url", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    ])
    _add_missing_columns(bind, "brand_wallet_designs", [
        sa.Column("background_image_url", sa.Text(), nullable=True),
        sa.Column("strip_url", sa.Text(), nullable=True),
        sa.Column("layout_style", sa.String(30), nullable=False, server_default="classic"),
        sa.Column("overlay_opacity", sa.Integer(), nullable=False, server_default="25"),
    ])

    # Backfill safe slugs before the application starts requiring them.
    stamp_table = Base.metadata.tables.get("stamp_programs")
    brand_table = Base.metadata.tables.get("brands")
    now = datetime.now(timezone.utc)
    if stamp_table is not None:
        rows = bind.execute(select(stamp_table.c.id, stamp_table.c.brand_id, stamp_table.c.name, stamp_table.c.slug)).mappings().all()
        used: set[tuple[uuid.UUID, str]] = set()
        for row in rows:
            candidate = row.get("slug") or _slug(row.get("name") or "", f"card-{str(row['id'])[:8]}")
            base = candidate
            suffix = 2
            while (row["brand_id"], candidate) in used:
                candidate = f"{base[:70]}-{suffix}"
                suffix += 1
            used.add((row["brand_id"], candidate))
            if row.get("slug") != candidate:
                bind.execute(stamp_table.update().where(stamp_table.c.id == row["id"]).values(slug=candidate))

    # Every existing brand receives a default card without deleting any legacy data.
    if brand_table is not None and stamp_table is not None:
        for brand in bind.execute(select(brand_table)).mappings().all():
            existing = bind.execute(select(stamp_table.c.id).where(stamp_table.c.brand_id == brand["id"])).first()
            if not existing:
                bind.execute(stamp_table.insert().values(
                    id=uuid.uuid4(), brand_id=brand["id"], name="البطاقة الرئيسية", slug="main-card",
                    description="بطاقة الأختام الافتراضية", required_stamps=10,
                    reward_title="مكافأة مجانية", reward_type="free_item", stamp_icon="coffee",
                    background_color=brand.get("primary_color") or "#111827",
                    accent_color=brand.get("accent_color") or "#C6FF4A",
                    is_default=True, sort_order=0, is_active=True, created_at=now, updated_at=now,
                ))

    bind.execute(text("UPDATE brands SET program_mode='full' WHERE program_mode IS NULL OR program_mode=''"))


def downgrade() -> None:
    # Production downgrade intentionally keeps customer and stamp history.
    pass
