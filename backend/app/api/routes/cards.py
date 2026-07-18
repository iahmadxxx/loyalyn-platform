from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import brand_access, current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import (
    Brand, CardTemplate, CardTemplateProgram, Customer, CustomerCardAssignment,
    StampProgram, WalletPass,
)
from app.schemas.common import CardTemplateCreate, CardTemplateUpdate, CustomerCardAssignmentUpdate
from app.services.audit import add_audit
from app.services.capabilities import brand_capabilities
from app.services.cards import (
    assign_template, ensure_default_template, make_published_snapshot, set_template_programs, template_out,
)
from app.services.wallet import push_pass_update

router = APIRouter()
settings = get_settings()


async def require_card_feature(db: AsyncSession, brand_id: uuid.UUID) -> Brand:
    brand = await db.get(Brand, brand_id)
    if not brand or not brand.is_active:
        raise HTTPException(404, "البراند غير موجود أو موقوف")
    if not brand_capabilities(brand).get("stamps"):
        raise HTTPException(409, "بطاقات الأختام غير مفعلة لهذا البراند")
    return brand


async def unique_slug(db: AsyncSession, brand_id: uuid.UUID, base: str, *, exclude: uuid.UUID | None = None) -> str:
    root = base.strip().lower()[:70] or "card"
    candidate = root
    counter = 2
    while True:
        query = select(CardTemplate).where(CardTemplate.brand_id == brand_id, CardTemplate.slug == candidate)
        if exclude:
            query = query.where(CardTemplate.id != exclude)
        if not await db.scalar(query):
            return candidate
        candidate = f"{root[:65]}-{counter}"
        counter += 1


@router.get("/templates")
async def list_templates(
    brand_id: uuid.UUID,
    include_archived: bool = True,
    public_only: bool = False,
    db: AsyncSession = Depends(get_db),
    user=Depends(current_user),
):
    await brand_access(db, user, brand_id, permission="loyalty.view")
    brand = await require_card_feature(db, brand_id)
    await ensure_default_template(db, brand)
    await db.commit()
    query = select(CardTemplate).where(CardTemplate.brand_id == brand_id)
    if not include_archived:
        query = query.where(CardTemplate.status != "archived")
    if public_only:
        query = query.where(CardTemplate.status == "published", CardTemplate.allow_public_join.is_(True))
    rows = list((await db.scalars(query.order_by(CardTemplate.sort_order, CardTemplate.created_at))).all())
    return [await template_out(db, row) for row in rows]


@router.post("/templates", status_code=201)
async def create_template(
    payload: CardTemplateCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(current_user),
):
    await brand_access(db, user, payload.brand_id, permission="loyalty.manage")
    brand = await require_card_feature(db, payload.brand_id)
    if await db.scalar(select(CardTemplate).where(CardTemplate.brand_id == payload.brand_id, CardTemplate.slug == payload.slug)):
        raise HTTPException(409, "الرابط الداخلي مستخدم في بطاقة أخرى")
    data = payload.model_dump(exclude={"program_ids"})
    if payload.is_default:
        for item in (await db.scalars(select(CardTemplate).where(CardTemplate.brand_id == payload.brand_id))).all():
            item.is_default = False
    template = CardTemplate(**data, status="draft")
    db.add(template)
    await db.flush()
    try:
        await set_template_programs(db, template, payload.program_ids)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not payload.program_ids:
        programs = list((await db.scalars(
            select(StampProgram).where(
                StampProgram.brand_id == payload.brand_id,
                StampProgram.is_active.is_(True),
                StampProgram.is_archived.is_(False),
            ).order_by(StampProgram.sort_order, StampProgram.created_at)
        )).all())
        await set_template_programs(db, template, [x.id for x in programs])
    add_audit(
        db, actor_id=user.id, action="card_template_created", entity_type="card_template",
        entity_id=template.id, brand_id=payload.brand_id,
        details={"name": template.name, "program_count": len(payload.program_ids)},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(template)
    return await template_out(db, template)


@router.patch("/templates/{template_id}")
async def update_template(
    template_id: uuid.UUID,
    payload: CardTemplateUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(current_user),
):
    template = await db.get(CardTemplate, template_id)
    if not template:
        raise HTTPException(404, "البطاقة غير موجودة")
    await brand_access(db, user, template.brand_id, permission="loyalty.manage")
    await require_card_feature(db, template.brand_id)
    data = payload.model_dump(exclude_unset=True)
    program_ids = data.pop("program_ids", None)
    if "slug" in data:
        duplicate = await db.scalar(select(CardTemplate).where(
            CardTemplate.brand_id == template.brand_id,
            CardTemplate.slug == data["slug"], CardTemplate.id != template.id,
        ))
        if duplicate:
            raise HTTPException(409, "الرابط الداخلي مستخدم في بطاقة أخرى")
    if data.get("is_default"):
        for item in (await db.scalars(select(CardTemplate).where(CardTemplate.brand_id == template.brand_id, CardTemplate.id != template.id))).all():
            item.is_default = False
    design_fields = {
        "background_color", "foreground_color", "label_color", "logo_text", "card_title",
        "layout_style", "overlay_opacity", "barcode_format", "fields", "terms",
    }
    if any(key in data for key in design_fields):
        template.draft_version += 1
    for key, value in data.items():
        setattr(template, key, value)
    if program_ids is not None:
        try:
            await set_template_programs(db, template, program_ids)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    add_audit(
        db, actor_id=user.id, action="card_template_updated", entity_type="card_template",
        entity_id=template.id, brand_id=template.brand_id,
        details={"fields": list(data), "programs_changed": program_ids is not None},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(template)
    return await template_out(db, template)


@router.post("/templates/{template_id}/publish")
async def publish_template(template_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    template = await db.get(CardTemplate, template_id)
    if not template:
        raise HTTPException(404, "البطاقة غير موجودة")
    await brand_access(db, user, template.brand_id, permission="wallet.design")
    count = int(await db.scalar(select(func.count()).select_from(CardTemplateProgram).where(CardTemplateProgram.card_template_id == template.id)) or 0)
    if count < 1:
        raise HTTPException(409, "أضف برنامج ختم واحدًا على الأقل قبل نشر البطاقة")
    template.status = "published"
    template.archived_at = None
    template.published_snapshot = await make_published_snapshot(db, template)
    template.published_version = template.draft_version
    passes = list((await db.scalars(select(WalletPass).where(WalletPass.card_template_id == template.id, WalletPass.status == "active"))).all())
    for wallet_pass in passes:
        wallet_pass.update_tag += 1
    add_audit(db, actor_id=user.id, action="card_template_published", entity_type="card_template", entity_id=template.id, brand_id=template.brand_id, details={"version": template.published_version, "passes": len(passes)}, ip_address=request.client.host if request.client else None)
    await db.commit()
    for wallet_pass in passes:
        await push_pass_update(db, wallet_pass)
    if passes:
        await db.commit()
    return await template_out(db, template)


@router.post("/templates/{template_id}/unpublish")
async def unpublish_template(template_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    template = await db.get(CardTemplate, template_id)
    if not template:
        raise HTTPException(404, "البطاقة غير موجودة")
    await brand_access(db, user, template.brand_id, permission="wallet.design")
    usage = int(await db.scalar(select(func.count()).select_from(CustomerCardAssignment).where(CustomerCardAssignment.card_template_id == template.id)) or 0)
    if usage:
        raise HTTPException(409, "لا يمكن إلغاء نشر بطاقة مستخدمة؛ أنشئ بديلًا وانقل العملاء أو أرشفها")
    template.status = "draft"
    template.allow_public_join = False
    add_audit(db, actor_id=user.id, action="card_template_unpublished", entity_type="card_template", entity_id=template.id, brand_id=template.brand_id, details={}, ip_address=request.client.host if request.client else None)
    await db.commit()
    return await template_out(db, template)


@router.post("/templates/{template_id}/duplicate", status_code=201)
async def duplicate_template(template_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    source = await db.get(CardTemplate, template_id)
    if not source:
        raise HTTPException(404, "البطاقة غير موجودة")
    await brand_access(db, user, source.brand_id, permission="loyalty.manage")
    slug = await unique_slug(db, source.brand_id, f"{source.slug}-copy")
    clone = CardTemplate(
        brand_id=source.brand_id, name=f"نسخة من {source.name}", name_en=source.name_en,
        slug=slug, description=source.description, status="draft", is_default=False,
        allow_public_join=False, sort_order=source.sort_order + 1,
        background_color=source.background_color, foreground_color=source.foreground_color,
        label_color=source.label_color, logo_text=source.logo_text, card_title=source.card_title,
        logo_url=source.logo_url, hero_url=source.hero_url,
        background_image_url=source.background_image_url, strip_url=source.strip_url,
        layout_style=source.layout_style, overlay_opacity=source.overlay_opacity,
        barcode_format=source.barcode_format, fields=dict(source.fields or {}), terms=source.terms,
    )
    db.add(clone)
    await db.flush()
    rows = list((await db.scalars(select(CardTemplateProgram).where(CardTemplateProgram.card_template_id == source.id).order_by(CardTemplateProgram.sort_order))).all())
    for row in rows:
        db.add(CardTemplateProgram(card_template_id=clone.id, stamp_program_id=row.stamp_program_id, sort_order=row.sort_order, is_visible=row.is_visible))
    add_audit(db, actor_id=user.id, action="card_template_duplicated", entity_type="card_template", entity_id=clone.id, brand_id=clone.brand_id, details={"source_id": str(source.id)}, ip_address=request.client.host if request.client else None)
    await db.commit()
    await db.refresh(clone)
    return await template_out(db, clone)


@router.post("/templates/{template_id}/archive")
async def archive_template(template_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    template = await db.get(CardTemplate, template_id)
    if not template:
        raise HTTPException(404, "البطاقة غير موجودة")
    await brand_access(db, user, template.brand_id, permission="loyalty.manage")
    replacements = list((await db.scalars(select(CardTemplate).where(
        CardTemplate.brand_id == template.brand_id,
        CardTemplate.id != template.id,
        CardTemplate.status == "published",
    ).order_by(CardTemplate.is_default.desc(), CardTemplate.sort_order, CardTemplate.created_at))).all())
    usage = int(await db.scalar(select(func.count()).select_from(CustomerCardAssignment).where(CustomerCardAssignment.card_template_id == template.id)) or 0)
    if usage and not replacements:
        raise HTTPException(409, "لا يمكن أرشفة البطاقة المستخدمة قبل نشر بطاقة بديلة")
    replacement = replacements[0] if replacements else None
    if replacement:
        assignments = list((await db.scalars(select(CustomerCardAssignment).where(CustomerCardAssignment.card_template_id == template.id))).all())
        for assignment in assignments:
            customer = await db.get(Customer, assignment.customer_id)
            await assign_template(db, customer, replacement, actor_id=user.id)
    template.status = "archived"
    template.archived_at = datetime.now(timezone.utc)
    template.allow_public_join = False
    if template.is_default:
        template.is_default = False
        if replacement:
            replacement.is_default = True
    add_audit(db, actor_id=user.id, action="card_template_archived", entity_type="card_template", entity_id=template.id, brand_id=template.brand_id, details={"reassigned_customers": usage, "replacement_id": str(replacement.id) if replacement else None}, ip_address=request.client.host if request.client else None)
    await db.commit()
    return await template_out(db, template)


@router.post("/templates/{template_id}/restore")
async def restore_template(template_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    template = await db.get(CardTemplate, template_id)
    if not template:
        raise HTTPException(404, "البطاقة غير موجودة")
    await brand_access(db, user, template.brand_id, permission="loyalty.manage")
    template.status = "draft"
    template.archived_at = None
    add_audit(db, actor_id=user.id, action="card_template_restored", entity_type="card_template", entity_id=template.id, brand_id=template.brand_id, details={}, ip_address=request.client.host if request.client else None)
    await db.commit()
    return await template_out(db, template)


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(template_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    template = await db.get(CardTemplate, template_id)
    if not template:
        raise HTTPException(404, "البطاقة غير موجودة")
    await brand_access(db, user, template.brand_id, permission="loyalty.manage")
    usage = int(await db.scalar(select(func.count()).select_from(CustomerCardAssignment).where(CustomerCardAssignment.card_template_id == template.id)) or 0)
    passes = int(await db.scalar(select(func.count()).select_from(WalletPass).where(WalletPass.card_template_id == template.id)) or 0)
    if usage or passes:
        raise HTTPException(409, "البطاقة مستخدمة؛ استخدم الأرشفة بدل الحذف النهائي")
    await db.delete(template)
    add_audit(db, actor_id=user.id, action="card_template_deleted", entity_type="card_template", entity_id=template.id, brand_id=template.brand_id, details={}, ip_address=request.client.host if request.client else None)
    await db.commit()


@router.post("/templates/{template_id}/asset")
async def upload_template_asset(
    template_id: uuid.UUID,
    kind: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(current_user),
):
    template = await db.get(CardTemplate, template_id)
    if not template:
        raise HTTPException(404, "البطاقة غير موجودة")
    await brand_access(db, user, template.brand_id, permission="wallet.design")
    if kind not in {"logo", "hero", "background", "strip"}:
        raise HTTPException(400, "نوع الصورة غير صحيح")
    if not file.filename or not file.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        raise HTTPException(400, "الصورة يجب أن تكون PNG أو JPG أو WebP")
    raw = await file.read()
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(413, "حجم الصورة أكبر من 10MB")
    folder = settings.wallet_path / "card-templates" / str(template.id)
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / f"{kind}.source{Path(file.filename).suffix.lower()}"
    destination.write_bytes(raw)
    try:
        from PIL import Image
        with Image.open(destination) as image:
            image.verify()
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(400, "ملف الصورة تالف أو غير مدعوم") from exc
    value = f"storage://{destination}"
    setattr(template, {"logo": "logo_url", "hero": "hero_url", "background": "background_image_url", "strip": "strip_url"}[kind], value)
    template.draft_version += 1
    await db.commit()
    return {"ok": True, "kind": kind, "asset_url": f"{settings.public_api_url.rstrip('/')}/api/cards/public/assets/{template.id}/{kind}"}


@router.delete("/templates/{template_id}/asset/{kind}", status_code=204)
async def delete_template_asset(template_id: uuid.UUID, kind: str, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    template = await db.get(CardTemplate, template_id)
    if not template:
        raise HTTPException(404, "البطاقة غير موجودة")
    await brand_access(db, user, template.brand_id, permission="wallet.design")
    if kind not in {"logo", "hero", "background", "strip"}:
        raise HTTPException(400, "نوع الصورة غير صحيح")
    field = {"logo": "logo_url", "hero": "hero_url", "background": "background_image_url", "strip": "strip_url"}[kind]
    value = getattr(template, field)
    if value and value.startswith("storage://"):
        Path(value.removeprefix("storage://")).unlink(missing_ok=True)
    setattr(template, field, None)
    template.draft_version += 1
    await db.commit()


@router.get("/public/assets/{template_id}/{kind}")
async def public_template_asset(template_id: uuid.UUID, kind: str, version: str | None = None, db: AsyncSession = Depends(get_db)):
    template = await db.get(CardTemplate, template_id)
    if not template or kind not in {"logo", "hero", "background", "strip"}:
        raise HTTPException(404, "الصورة غير موجودة")
    if version == "published" and template.published_snapshot:
        snapshot = dict(template.published_snapshot or {})
        value = {"logo": snapshot.get("logo_url"), "hero": snapshot.get("hero_url"), "background": snapshot.get("background_image_url"), "strip": snapshot.get("strip_url")}[kind]
    else:
        value = {"logo": template.logo_url, "hero": template.hero_url, "background": template.background_image_url, "strip": template.strip_url}[kind]
    if not value or not value.startswith("storage://"):
        raise HTTPException(404, "الصورة غير موجودة")
    path = Path(value.removeprefix("storage://"))
    if not path.exists():
        raise HTTPException(404, "الصورة غير موجودة")
    return FileResponse(path)


@router.get("/customers/{customer_id}/assignment")
async def get_customer_assignment(customer_id: uuid.UUID, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(404, "العميل غير موجود")
    await brand_access(db, user, customer.brand_id, permission="customers.view")
    assignment = await db.scalar(select(CustomerCardAssignment).where(CustomerCardAssignment.customer_id == customer.id))
    if not assignment:
        brand = await db.get(Brand, customer.brand_id)
        template = await ensure_default_template(db, brand)
        assignment = await assign_template(db, customer, template)
        await db.commit()
    template = await db.get(CardTemplate, assignment.card_template_id)
    return {"assignment_id": str(assignment.id), "card_template": await template_out(db, template)}


@router.put("/customers/{customer_id}/assignment")
async def update_customer_assignment(
    customer_id: uuid.UUID,
    payload: CustomerCardAssignmentUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(current_user),
):
    customer = await db.get(Customer, customer_id)
    template = await db.get(CardTemplate, payload.card_template_id)
    if not customer or not template or template.brand_id != customer.brand_id:
        raise HTTPException(404, "العميل أو البطاقة غير موجودة")
    if template.status != "published":
        raise HTTPException(409, "انشر البطاقة أولًا قبل ربطها بالعميل")
    await brand_access(db, user, customer.brand_id, permission="customers.edit")
    try:
        assignment = await assign_template(db, customer, template, actor_id=user.id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    wallet_pass = await db.scalar(select(WalletPass).where(WalletPass.customer_id == customer.id, WalletPass.status == "active"))
    add_audit(db, actor_id=user.id, action="customer_card_template_changed", entity_type="customer", entity_id=customer.id, brand_id=customer.brand_id, details={"template_id": str(template.id)}, ip_address=request.client.host if request.client else None)
    await db.commit()
    if wallet_pass:
        await push_pass_update(db, wallet_pass)
        await db.commit()
    return {"assignment_id": str(assignment.id), "card_template": await template_out(db, template)}
