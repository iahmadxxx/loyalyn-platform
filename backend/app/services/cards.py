from __future__ import annotations

import uuid
from types import SimpleNamespace
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    Brand,
    BrandWalletDesign,
    CardTemplate,
    CardTemplateProgram,
    Customer,
    CustomerCardAssignment,
    CustomerStampCard,
    StampProgram,
    WalletPass,
)

settings = get_settings()

DEFAULT_FIELDS = {
    "show_points": False,
    "show_stamps": True,
    "show_rewards": True,
    "show_tier": False,
    "show_visits": False,
}

SNAPSHOT_FIELDS = (
    "name",
    "name_en",
    "description",
    "background_color",
    "foreground_color",
    "label_color",
    "logo_text",
    "card_title",
    "logo_url",
    "hero_url",
    "background_image_url",
    "strip_url",
    "layout_style",
    "overlay_opacity",
    "barcode_format",
    "fields",
    "terms",
)


def public_asset_value(template: CardTemplate, kind: str, value: str | None, *, published: bool = False) -> str | None:
    if not value:
        return None
    if value.startswith("storage://"):
        suffix = "?version=published" if published else ""
        return f"{settings.public_api_url.rstrip('/')}/api/cards/public/assets/{template.id}/{kind}{suffix}"
    return value


def program_summary(program: StampProgram) -> dict:
    return {
        "id": str(program.id),
        "name": program.name,
        "slug": program.slug,
        "description": program.description,
        "required_stamps": program.required_stamps,
        "reward_title": program.reward_title,
        "reward_type": program.reward_type,
        "stamp_icon": program.stamp_icon,
        "background_color": program.background_color,
        "accent_color": program.accent_color,
        "card_image_url": f"{settings.public_api_url.rstrip('/')}/api/stamps/public/assets/{program.id}/card" if program.card_image_url else None,
        "empty_stamp_image_url": f"{settings.public_api_url.rstrip('/')}/api/stamps/public/assets/{program.id}/empty_stamp" if program.empty_stamp_image_url else None,
        "filled_stamp_image_url": f"{settings.public_api_url.rstrip('/')}/api/stamps/public/assets/{program.id}/filled_stamp" if program.filled_stamp_image_url else None,
        "display_options": dict(program.display_options or {}),
        "sort_order": program.sort_order,
        "is_active": program.is_active,
        "is_archived": getattr(program, "is_archived", False),
    }


async def _draft_program_rows(
    db: AsyncSession,
    template_id: uuid.UUID,
    *,
    active_only: bool = False,
) -> list[tuple[CardTemplateProgram, StampProgram]]:
    query = (
        select(CardTemplateProgram, StampProgram)
        .join(StampProgram, StampProgram.id == CardTemplateProgram.stamp_program_id)
        .where(CardTemplateProgram.card_template_id == template_id)
        .order_by(CardTemplateProgram.sort_order, StampProgram.sort_order, StampProgram.created_at)
    )
    if active_only:
        query = query.where(
            CardTemplateProgram.is_visible.is_(True),
            StampProgram.is_active.is_(True),
            StampProgram.is_archived.is_(False),
        )
    return list((await db.execute(query)).all())


async def template_program_rows(
    db: AsyncSession,
    template_id: uuid.UUID,
    *,
    active_only: bool = False,
    published: bool = False,
) -> list[tuple[CardTemplateProgram | SimpleNamespace, StampProgram]]:
    if not published:
        return await _draft_program_rows(db, template_id, active_only=active_only)
    template = await db.get(CardTemplate, template_id)
    snapshot = dict(template.published_snapshot or {}) if template else {}
    raw_ids = list(snapshot.get("program_ids") or [])
    try:
        program_ids = [uuid.UUID(str(value)) for value in raw_ids]
    except (TypeError, ValueError, AttributeError):
        program_ids = []
    if not program_ids:
        # Legacy published templates created before snapshot support use the
        # current links once, then are snapshotted on their next publish.
        return await _draft_program_rows(db, template_id, active_only=active_only)
    rows = list((await db.scalars(select(StampProgram).where(StampProgram.id.in_(program_ids)))).all())
    by_id = {row.id: row for row in rows}
    output: list[tuple[SimpleNamespace, StampProgram]] = []
    for index, program_id in enumerate(program_ids):
        program = by_id.get(program_id)
        if not program:
            continue
        if active_only and (not program.is_active or program.is_archived):
            continue
        output.append((SimpleNamespace(sort_order=index, is_visible=True), program))
    return output


async def make_published_snapshot(db: AsyncSession, template: CardTemplate) -> dict:
    rows = await _draft_program_rows(db, template.id)
    snapshot = {field: getattr(template, field) for field in SNAPSHOT_FIELDS}
    snapshot["fields"] = dict(template.fields or DEFAULT_FIELDS)
    snapshot["program_ids"] = [str(program.id) for _, program in rows]
    snapshot["published_version"] = template.draft_version
    return snapshot


def published_design(template: CardTemplate) -> CardTemplate | SimpleNamespace:
    snapshot = dict(template.published_snapshot or {})
    if not snapshot:
        return template
    values = {field: snapshot.get(field, getattr(template, field)) for field in SNAPSHOT_FIELDS}
    values["id"] = template.id
    values["brand_id"] = template.brand_id
    values["status"] = template.status
    values["published_version"] = template.published_version
    return SimpleNamespace(**values)


async def template_out(
    db: AsyncSession,
    template: CardTemplate,
    *,
    include_usage: bool = True,
    published_view: bool = False,
) -> dict:
    snapshot = dict(template.published_snapshot or {}) if published_view else {}
    source = published_design(template) if published_view else template
    program_rows = await template_program_rows(db, template.id, published=published_view)
    usage_count = 0
    if include_usage:
        usage_count = int(
            await db.scalar(
                select(func.count())
                .select_from(CustomerCardAssignment)
                .where(CustomerCardAssignment.card_template_id == template.id)
            )
            or 0
        )
    return {
        "id": str(template.id),
        "brand_id": str(template.brand_id),
        "name": source.name,
        "name_en": source.name_en,
        "slug": template.slug,
        "description": source.description,
        "status": template.status,
        "is_default": template.is_default,
        "allow_public_join": template.allow_public_join,
        "sort_order": template.sort_order,
        "background_color": source.background_color,
        "foreground_color": source.foreground_color,
        "label_color": source.label_color,
        "logo_text": source.logo_text,
        "card_title": source.card_title,
        "logo_url": public_asset_value(template, "logo", source.logo_url, published=published_view),
        "hero_url": public_asset_value(template, "hero", source.hero_url, published=published_view),
        "background_image_url": public_asset_value(template, "background", source.background_image_url, published=published_view),
        "strip_url": public_asset_value(template, "strip", source.strip_url, published=published_view),
        "layout_style": source.layout_style,
        "overlay_opacity": source.overlay_opacity,
        "barcode_format": source.barcode_format,
        "fields": source.fields or dict(DEFAULT_FIELDS),
        "terms": source.terms,
        "draft_version": template.draft_version,
        "published_version": template.published_version,
        "has_unpublished_changes": template.draft_version != template.published_version,
        "published_snapshot_ready": bool(snapshot or template.published_version),
        "archived_at": template.archived_at,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
        "programs": [
            program_summary(program)
            | {"template_sort_order": link.sort_order, "is_visible": link.is_visible}
            for link, program in program_rows
        ],
        "program_ids": [str(program.id) for _, program in program_rows],
        "usage_count": usage_count,
    }


async def set_template_programs(db: AsyncSession, template: CardTemplate, program_ids: list[uuid.UUID]) -> None:
    unique_ids = list(dict.fromkeys(program_ids))
    if unique_ids:
        programs = list((await db.scalars(select(StampProgram).where(StampProgram.id.in_(unique_ids)))).all())
        found = {program.id: program for program in programs}
        if len(found) != len(unique_ids) or any(program.brand_id != template.brand_id for program in programs):
            raise ValueError("أحد برامج الأختام غير موجود داخل هذا البراند")
        if any(program.is_archived for program in programs):
            raise ValueError("لا يمكن إضافة برنامج ختم مؤرشف إلى البطاقة")
    await db.execute(delete(CardTemplateProgram).where(CardTemplateProgram.card_template_id == template.id))
    for index, program_id in enumerate(unique_ids):
        db.add(
            CardTemplateProgram(
                card_template_id=template.id,
                stamp_program_id=program_id,
                sort_order=index,
                is_visible=True,
            )
        )
    template.draft_version += 1


async def ensure_default_template(db: AsyncSession, brand: Brand) -> CardTemplate:
    template = await db.scalar(
        select(CardTemplate)
        .where(
            CardTemplate.brand_id == brand.id,
            CardTemplate.is_default.is_(True),
            CardTemplate.status != "archived",
        )
        .order_by(CardTemplate.created_at)
    )
    if template:
        return template
    template = await db.scalar(
        select(CardTemplate)
        .where(CardTemplate.brand_id == brand.id, CardTemplate.status != "archived")
        .order_by(CardTemplate.sort_order, CardTemplate.created_at)
    )
    if template:
        template.is_default = True
        return template
    design = await db.scalar(select(BrandWalletDesign).where(BrandWalletDesign.brand_id == brand.id))
    template = CardTemplate(
        brand_id=brand.id,
        name=f"بطاقة {brand.name}",
        name_en=f"{brand.name} Card",
        slug="main-card",
        description="البطاقة الرئيسية الافتراضية",
        status="published",
        is_default=True,
        allow_public_join=True,
        sort_order=0,
        background_color=(design.background_color if design else brand.primary_color),
        foreground_color=(design.foreground_color if design else "#FFFFFF"),
        label_color=(design.label_color if design else brand.accent_color),
        logo_text=(design.logo_text if design else brand.name),
        card_title=(design.card_title if design else "بطاقة الولاء"),
        logo_url=(design.logo_url if design else None),
        hero_url=(design.hero_url if design else None),
        background_image_url=(design.background_image_url if design else None),
        strip_url=(design.strip_url if design else None),
        layout_style=(design.layout_style if design else "classic"),
        overlay_opacity=(design.overlay_opacity if design else 25),
        barcode_format=(design.barcode_format if design else "PKBarcodeFormatQR"),
        fields=(dict(design.fields or DEFAULT_FIELDS) if design else dict(DEFAULT_FIELDS)),
        terms=(design.terms if design else None),
        published_version=1,
    )
    db.add(template)
    await db.flush()
    programs = list(
        (
            await db.scalars(
                select(StampProgram)
                .where(
                    StampProgram.brand_id == brand.id,
                    StampProgram.is_active.is_(True),
                    StampProgram.is_archived.is_(False),
                )
                .order_by(StampProgram.sort_order, StampProgram.created_at)
            )
        ).all()
    )
    for index, program in enumerate(programs):
        db.add(
            CardTemplateProgram(
                card_template_id=template.id,
                stamp_program_id=program.id,
                sort_order=index,
                is_visible=True,
            )
        )
    await db.flush()
    template.published_snapshot = await make_published_snapshot(db, template)
    template.published_version = template.draft_version
    return template


async def assigned_templates_for_customer(
    db: AsyncSession,
    customer: Customer,
    *,
    include_draft: bool = False,
    ensure_fallback: bool = True,
) -> list[tuple[CustomerCardAssignment, CardTemplate]]:
    query = (
        select(CustomerCardAssignment, CardTemplate)
        .join(CardTemplate, CardTemplate.id == CustomerCardAssignment.card_template_id)
        .where(
            CustomerCardAssignment.customer_id == customer.id,
            CustomerCardAssignment.is_active.is_(True),
            CardTemplate.brand_id == customer.brand_id,
            CardTemplate.status != "archived",
        )
        .order_by(CardTemplate.sort_order, CardTemplate.created_at)
    )
    if not include_draft:
        query = query.where(CardTemplate.status == "published")
    rows = list((await db.execute(query)).all())
    if rows or not ensure_fallback:
        return rows
    brand = await db.get(Brand, customer.brand_id)
    template = await db.scalar(
        select(CardTemplate)
        .where(CardTemplate.brand_id == customer.brand_id, CardTemplate.status == "published")
        .order_by(CardTemplate.is_default.desc(), CardTemplate.sort_order, CardTemplate.created_at)
    )
    if not template:
        template = await ensure_default_template(db, brand)
    assignment = await attach_template(db, customer, template)
    return [(assignment, template)]


async def active_template_for_customer(
    db: AsyncSession,
    customer: Customer,
) -> tuple[CustomerCardAssignment, CardTemplate]:
    """Backward-compatible primary card lookup.

    V6 supports several active cards per customer. Legacy callers still receive
    the first active published card, ordered by the card studio sort order.
    """
    rows = await assigned_templates_for_customer(db, customer)
    return rows[0]


async def attach_template(
    db: AsyncSession,
    customer: Customer,
    template: CardTemplate,
    *,
    actor_id: uuid.UUID | None = None,
) -> CustomerCardAssignment:
    if template.brand_id != customer.brand_id or template.status == "archived":
        raise ValueError("البطاقة غير متاحة لهذا العميل")
    assignment = await db.scalar(
        select(CustomerCardAssignment).where(
            CustomerCardAssignment.customer_id == customer.id,
            CustomerCardAssignment.card_template_id == template.id,
        )
    )
    if assignment:
        assignment.brand_id = customer.brand_id
        assignment.assigned_by_actor_id = actor_id
        assignment.is_active = True
    else:
        assignment = CustomerCardAssignment(
            brand_id=customer.brand_id,
            customer_id=customer.id,
            card_template_id=template.id,
            assigned_by_actor_id=actor_id,
            is_active=True,
        )
        db.add(assignment)
        await db.flush()
    await sync_customer_cards_to_assignments(db, customer)
    return assignment


async def detach_template(
    db: AsyncSession,
    customer: Customer,
    template: CardTemplate,
) -> CustomerCardAssignment | None:
    assignment = await db.scalar(
        select(CustomerCardAssignment).where(
            CustomerCardAssignment.customer_id == customer.id,
            CustomerCardAssignment.card_template_id == template.id,
        )
    )
    if assignment:
        assignment.is_active = False
    wallet_pass = await db.scalar(
        select(WalletPass).where(
            WalletPass.customer_id == customer.id,
            WalletPass.card_template_id == template.id,
            WalletPass.status == "active",
        )
    )
    if wallet_pass:
        wallet_pass.status = "revoked"
        wallet_pass.update_tag += 1
    await sync_customer_cards_to_assignments(db, customer)
    return assignment


async def assign_template(
    db: AsyncSession,
    customer: Customer,
    template: CardTemplate,
    *,
    actor_id: uuid.UUID | None = None,
) -> CustomerCardAssignment:
    """Legacy single-card operation used by older clients.

    The new studio uses attach_template and lets several cards stay active.
    This method intentionally keeps the historical replace behavior.
    """
    rows = list((await db.scalars(
        select(CustomerCardAssignment).where(CustomerCardAssignment.customer_id == customer.id)
    )).all())
    for row in rows:
        row.is_active = row.card_template_id == template.id
    assignment = await attach_template(db, customer, template, actor_id=actor_id)
    for wallet_pass in (await db.scalars(
        select(WalletPass).where(WalletPass.customer_id == customer.id, WalletPass.status == "active")
    )).all():
        if wallet_pass.card_template_id != template.id:
            wallet_pass.status = "revoked"
            wallet_pass.update_tag += 1
    return assignment


async def sync_customer_cards_to_assignments(
    db: AsyncSession,
    customer: Customer,
) -> list[tuple[CustomerStampCard, StampProgram]]:
    assigned = await assigned_templates_for_customer(
        db, customer, include_draft=True, ensure_fallback=False
    )
    ordered_programs: list[StampProgram] = []
    seen: set[uuid.UUID] = set()
    for _, template in assigned:
        rows = await template_program_rows(
            db,
            template.id,
            active_only=True,
            published=template.status == "published",
        )
        for _, program in rows:
            if program.id not in seen:
                seen.add(program.id)
                ordered_programs.append(program)
    existing_rows = list((await db.scalars(
        select(CustomerStampCard).where(CustomerStampCard.customer_id == customer.id)
    )).all())
    existing = {row.stamp_program_id: row for row in existing_rows}
    for card in existing_rows:
        card.is_active = card.stamp_program_id in seen
    had_any = bool(existing)
    default_consumed = False
    result: list[tuple[CustomerStampCard, StampProgram]] = []
    for program in ordered_programs:
        card = existing.get(program.id)
        if not card:
            migrate_legacy = not had_any and not default_consumed
            card = CustomerStampCard(
                brand_id=customer.brand_id,
                customer_id=customer.id,
                stamp_program_id=program.id,
                stamps=customer.stamps if migrate_legacy else 0,
                rewards_available=customer.available_rewards if migrate_legacy else 0,
                lifetime_stamps=customer.stamps if migrate_legacy else 0,
                is_active=True,
            )
            db.add(card)
            await db.flush()
            existing[program.id] = card
            if migrate_legacy:
                default_consumed = True
        else:
            card.is_active = True
        result.append((card, program))
    return result


async def sync_customer_cards_to_template(
    db: AsyncSession,
    customer: Customer,
    template: CardTemplate,
) -> list[tuple[CustomerStampCard, StampProgram]]:
    await sync_customer_cards_to_assignments(db, customer)
    program_rows = await template_program_rows(
        db,
        template.id,
        active_only=True,
        published=template.status == "published",
    )
    program_ids = [program.id for _, program in program_rows]
    if not program_ids:
        return []
    cards = list((await db.scalars(
        select(CustomerStampCard).where(
            CustomerStampCard.customer_id == customer.id,
            CustomerStampCard.stamp_program_id.in_(program_ids),
        )
    )).all())
    by_program = {card.stamp_program_id: card for card in cards}
    return [(by_program[program.id], program) for _, program in program_rows if program.id in by_program]


async def customer_template_cards(
    db: AsyncSession,
    customer: Customer,
    template: CardTemplate | None = None,
) -> tuple[CardTemplate, list[tuple[CustomerStampCard, StampProgram]]]:
    if template is None:
        _, template = await active_template_for_customer(db, customer)
    rows = await sync_customer_cards_to_template(db, customer, template)
    return template, rows

