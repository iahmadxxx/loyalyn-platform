from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import brand_access, current_user, operational_branch
from app.core.config import get_settings
from app.db.session import get_db
from app.models import (
    Brand, Branch, CardTemplate, CardTemplateProgram, Customer, CustomerStampCard, StampProgram, StampTransaction, WalletPass,
)
from app.schemas.common import StampAction, StampProgramCreate, StampProgramUpdate, StampRedeem, StampTransactionReverse
from app.services.audit import add_audit
from app.services.capabilities import brand_capabilities
from app.services.cards import assigned_templates_for_customer, customer_template_cards, sync_customer_cards_to_assignments
from app.services.wallet import push_pass_update

router = APIRouter()
settings = get_settings()


def program_out(program: StampProgram) -> dict:
    return {
        "id": str(program.id), "brand_id": str(program.brand_id), "name": program.name,
        "slug": program.slug, "description": program.description,
        "required_stamps": program.required_stamps, "reward_title": program.reward_title,
        "reward_type": program.reward_type, "stamp_icon": program.stamp_icon,
        "background_color": program.background_color, "accent_color": program.accent_color,
        "card_image_url": f"{settings.public_api_url.rstrip('/')}/api/stamps/public/assets/{program.id}/card" if program.card_image_url else None,
        "empty_stamp_image_url": f"{settings.public_api_url.rstrip('/')}/api/stamps/public/assets/{program.id}/empty_stamp" if program.empty_stamp_image_url else None,
        "filled_stamp_image_url": f"{settings.public_api_url.rstrip('/')}/api/stamps/public/assets/{program.id}/filled_stamp" if program.filled_stamp_image_url else None,
        "display_options": dict(program.display_options or {}),
        "is_default": program.is_default, "sort_order": program.sort_order,
        "is_active": program.is_active, "is_archived": program.is_archived, "archived_at": program.archived_at,
        "created_at": program.created_at, "updated_at": program.updated_at,
    }


def card_out(card: CustomerStampCard, program: StampProgram) -> dict:
    data = program_out(program)
    data.update({
        "card_id": str(card.id), "customer_id": str(card.customer_id),
        "stamps": card.stamps, "rewards_available": card.rewards_available,
        "lifetime_stamps": card.lifetime_stamps, "last_stamp_at": card.last_stamp_at,
        "card_active": card.is_active,
    })
    return data


async def require_stamps(db: AsyncSession, brand_id: uuid.UUID) -> Brand:
    brand = await db.get(Brand, brand_id)
    if not brand or not brand.is_active:
        raise HTTPException(404, "البراند غير موجود أو موقوف")
    if not brand_capabilities(brand).get("stamps"):
        raise HTTPException(409, "ميزة بطاقات الأختام غير مفعلة لهذا البراند")
    return brand


async def ensure_branch(db: AsyncSession, branch_id: uuid.UUID | None, brand_id: uuid.UUID) -> None:
    if not branch_id:
        return
    branch = await db.get(Branch, branch_id)
    if not branch or branch.brand_id != brand_id or not branch.is_active:
        raise HTTPException(400, "الفرع غير موجود داخل هذا البراند أو أنه موقوف")


async def ensure_customer_cards(db: AsyncSession, customer: Customer) -> list[tuple[CustomerStampCard, StampProgram]]:
    return await sync_customer_cards_to_assignments(db, customer)


async def sync_customer_totals(db: AsyncSession, customer: Customer) -> None:
    totals = (await db.execute(
        select(
            func.coalesce(func.sum(CustomerStampCard.stamps), 0),
            func.coalesce(func.sum(CustomerStampCard.rewards_available), 0),
        ).where(CustomerStampCard.customer_id == customer.id, CustomerStampCard.is_active.is_(True))
    )).one()
    customer.stamps = int(totals[0] or 0)
    customer.available_rewards = int(totals[1] or 0)


async def mark_wallet_updates(db: AsyncSession, customer_id: uuid.UUID) -> list[WalletPass]:
    passes = list((await db.scalars(select(WalletPass).where(
        WalletPass.customer_id == customer_id, WalletPass.status == "active"
    ))).all())
    for wallet_pass in passes:
        wallet_pass.update_tag += 1
    return passes


@router.get("/programs")
async def list_programs(brand_id: uuid.UUID, active_only: bool = False, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, brand_id, permission="loyalty.view")
    await require_stamps(db, brand_id)
    query = select(StampProgram).where(StampProgram.brand_id == brand_id)
    if active_only:
        query = query.where(StampProgram.is_active.is_(True), StampProgram.is_archived.is_(False))
    rows = list((await db.scalars(query.order_by(StampProgram.sort_order, StampProgram.created_at))).all())
    return [program_out(x) for x in rows]


@router.post("/programs", status_code=201)
async def create_program(payload: StampProgramCreate, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, payload.brand_id, permission="loyalty.manage")
    await require_stamps(db, payload.brand_id)
    if await db.scalar(select(StampProgram).where(StampProgram.brand_id == payload.brand_id, StampProgram.slug == payload.slug)):
        raise HTTPException(409, "رابط بطاقة الأختام مستخدم داخل هذا البراند")
    if payload.is_default:
        for row in (await db.scalars(select(StampProgram).where(StampProgram.brand_id == payload.brand_id))).all():
            row.is_default = False
    program = StampProgram(**payload.model_dump())
    db.add(program)
    await db.flush()
    # V6 keeps stamp programs card-specific. The studio links the new
    # program to the currently edited card in the same save flow.
    add_audit(db, actor_id=user.id, action="stamp_program_created", entity_type="stamp_program", entity_id=program.id, brand_id=payload.brand_id, details={"name": program.name, "slug": program.slug}, ip_address=request.client.host if request.client else None)
    await db.commit()
    await db.refresh(program)
    return program_out(program)


@router.patch("/programs/{program_id}")
async def update_program(program_id: uuid.UUID, payload: StampProgramUpdate, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    program = await db.get(StampProgram, program_id)
    if not program:
        raise HTTPException(404, "بطاقة الأختام غير موجودة")
    await brand_access(db, user, program.brand_id, permission="loyalty.manage")
    await require_stamps(db, program.brand_id)
    data = payload.model_dump(exclude_unset=True)
    if "slug" in data:
        duplicate = await db.scalar(select(StampProgram).where(StampProgram.brand_id == program.brand_id, StampProgram.slug == data["slug"], StampProgram.id != program.id))
        if duplicate:
            raise HTTPException(409, "رابط بطاقة الأختام مستخدم داخل هذا البراند")
    if data.get("is_default"):
        for row in (await db.scalars(select(StampProgram).where(StampProgram.brand_id == program.brand_id, StampProgram.id != program.id))).all():
            row.is_default = False
    for field, value in data.items():
        setattr(program, field, value)
    add_audit(db, actor_id=user.id, action="stamp_program_updated", entity_type="stamp_program", entity_id=program.id, brand_id=program.brand_id, details=data, ip_address=request.client.host if request.client else None)
    await db.commit()
    await db.refresh(program)
    return program_out(program)


@router.post("/programs/{program_id}/archive")
async def archive_program(program_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    program = await db.get(StampProgram, program_id)
    if not program:
        raise HTTPException(404, "برنامج الختم غير موجود")
    await brand_access(db, user, program.brand_id, permission="loyalty.manage")
    program.is_active = False
    program.is_archived = True
    program.archived_at = datetime.now(timezone.utc)
    add_audit(db, actor_id=user.id, action="stamp_program_archived", entity_type="stamp_program", entity_id=program.id, brand_id=program.brand_id, details={"name": program.name}, ip_address=request.client.host if request.client else None)
    await db.commit()
    return program_out(program)


@router.post("/programs/{program_id}/restore")
async def restore_program(program_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    program = await db.get(StampProgram, program_id)
    if not program:
        raise HTTPException(404, "برنامج الختم غير موجود")
    await brand_access(db, user, program.brand_id, permission="loyalty.manage")
    program.is_archived = False
    program.archived_at = None
    program.is_active = True
    add_audit(db, actor_id=user.id, action="stamp_program_restored", entity_type="stamp_program", entity_id=program.id, brand_id=program.brand_id, details={"name": program.name}, ip_address=request.client.host if request.client else None)
    await db.commit()
    return program_out(program)


@router.delete("/programs/{program_id}", status_code=204)
async def delete_program(program_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    program = await db.get(StampProgram, program_id)
    if not program:
        raise HTTPException(404, "برنامج الختم غير موجود")
    await brand_access(db, user, program.brand_id, permission="loyalty.manage")
    linked = int(await db.scalar(select(func.count()).select_from(CardTemplateProgram).where(CardTemplateProgram.stamp_program_id == program.id)) or 0)
    cards = int(await db.scalar(select(func.count()).select_from(CustomerStampCard).where(CustomerStampCard.stamp_program_id == program.id)) or 0)
    transactions = int(await db.scalar(select(func.count()).select_from(StampTransaction).where(StampTransaction.stamp_program_id == program.id)) or 0)
    if linked or cards or transactions:
        raise HTTPException(409, "برنامج الختم مستخدم؛ استخدم الأرشفة بدل الحذف النهائي")
    await db.delete(program)
    add_audit(db, actor_id=user.id, action="stamp_program_deleted", entity_type="stamp_program", entity_id=program.id, brand_id=program.brand_id, details={"name": program.name}, ip_address=request.client.host if request.client else None)
    await db.commit()


@router.post("/programs/{program_id}/asset")
async def upload_program_asset(program_id: uuid.UUID, kind: str = Form(...), file: UploadFile = File(...), db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    program = await db.get(StampProgram, program_id)
    if not program:
        raise HTTPException(404, "بطاقة الأختام غير موجودة")
    await brand_access(db, user, program.brand_id, permission="loyalty.manage")
    if kind not in {"card", "empty_stamp", "filled_stamp"}:
        raise HTTPException(400, "نوع الصورة غير صحيح")
    if not file.filename or not file.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        raise HTTPException(400, "الصورة يجب أن تكون PNG أو JPG أو WebP")
    raw = await file.read()
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(413, "حجم الصورة أكبر من 8MB")
    folder = settings.wallet_path / "stamp-programs" / str(program.id)
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
    if kind == "card":
        program.card_image_url = value
    elif kind == "empty_stamp":
        program.empty_stamp_image_url = value
    else:
        program.filled_stamp_image_url = value
    await db.commit()
    return {"ok": True, "kind": kind, "asset_url": f"{settings.public_api_url.rstrip('/')}/api/stamps/public/assets/{program.id}/{kind}"}



@router.delete("/programs/{program_id}/asset/{kind}", status_code=204)
async def delete_program_asset(program_id: uuid.UUID, kind: str, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    program = await db.get(StampProgram, program_id)
    if not program or kind not in {"card", "empty_stamp", "filled_stamp"}:
        raise HTTPException(404, "الصورة غير موجودة")
    await brand_access(db, user, program.brand_id, permission="loyalty.manage")
    field = {"card": "card_image_url", "empty_stamp": "empty_stamp_image_url", "filled_stamp": "filled_stamp_image_url"}[kind]
    value = getattr(program, field)
    if value and value.startswith("storage://"):
        Path(value.removeprefix("storage://")).unlink(missing_ok=True)
    setattr(program, field, None)
    await db.commit()


@router.get("/public/assets/{program_id}/{kind}")
async def public_program_asset(program_id: uuid.UUID, kind: str, db: AsyncSession = Depends(get_db)):
    program = await db.get(StampProgram, program_id)
    if not program or kind not in {"card", "empty_stamp", "filled_stamp"}:
        raise HTTPException(404, "الصورة غير موجودة")
    value = {"card": program.card_image_url, "empty_stamp": program.empty_stamp_image_url, "filled_stamp": program.filled_stamp_image_url}[kind]
    if not value or not value.startswith("storage://"):
        raise HTTPException(404, "الصورة غير موجودة")
    path = Path(value.removeprefix("storage://"))
    if not path.exists():
        raise HTTPException(404, "الصورة غير موجودة")
    return FileResponse(path)


@router.get("/customers/{customer_id}/cards")
async def customer_cards(customer_id: uuid.UUID, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(404, "العميل غير موجود")
    await brand_access(db, user, customer.brand_id, permission="customers.view")
    await require_stamps(db, customer.brand_id)
    cards = await ensure_customer_cards(db, customer)
    await db.commit()
    return [card_out(card, program) for card, program in cards]


@router.get("/scan/{membership_code}")
async def scan_customer(membership_code: str, brand_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    code = membership_code.strip()
    query = select(Customer).where(Customer.membership_code == code, Customer.is_active.is_(True))
    if brand_id:
        query = query.where(Customer.brand_id == brand_id)
    customer = await db.scalar(query)
    if not customer:
        raise HTTPException(404, "لم يتم العثور على العميل من الرمز الممسوح")
    await brand_access(db, user, customer.brand_id, permission="loyalty.apply")
    brand = await require_stamps(db, customer.brand_id)
    assigned = await assigned_templates_for_customer(
        db, customer, ensure_fallback=False
    )
    template = assigned[0][1] if assigned else None
    cards = await ensure_customer_cards(db, customer)
    groups = []
    for _, assigned_template in assigned:
        _, template_cards = await customer_template_cards(db, customer, assigned_template)
        groups.append({
            "id": str(assigned_template.id), "name": assigned_template.name, "slug": assigned_template.slug,
            "cards": [card_out(card, program) for card, program in template_cards],
        })
    await db.commit()
    return {
        "brand": {"id": str(brand.id), "name": brand.name, "slug": brand.slug},
        "customer": {"id": str(customer.id), "name": customer.name, "phone": customer.phone, "membership_code": customer.membership_code, "last_visit_at": customer.last_visit_at},
        "card_template": ({"id": str(template.id), "name": template.name, "slug": template.slug} if template else None),
        "card_templates": groups,
        "cards": [card_out(card, program) for card, program in cards],
    }


@router.post("/customers/{customer_id}/programs/{program_id}/add")
async def add_stamps(customer_id: uuid.UUID, program_id: uuid.UUID, payload: StampAction, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    previous = await db.scalar(select(StampTransaction).where(StampTransaction.idempotency_key == payload.idempotency_key))
    if previous:
        customer = await db.get(Customer, previous.customer_id)
        cards = await ensure_customer_cards(db, customer)
        return {"duplicate": True, "customer": {"id": str(customer.id), "name": customer.name}, "cards": [card_out(c, p) for c, p in cards]}
    customer = await db.scalar(select(Customer).where(Customer.id == customer_id).with_for_update())
    program = await db.get(StampProgram, program_id)
    if not customer or not program or customer.brand_id != program.brand_id or not program.is_active:
        raise HTTPException(404, "العميل أو بطاقة الأختام غير موجودة")
    access = await brand_access(db, user, customer.brand_id, permission="loyalty.apply")
    branch_id = operational_branch(access, payload.branch_id)
    await require_stamps(db, customer.brand_id)
    await ensure_branch(db, branch_id, customer.brand_id)
    await ensure_customer_cards(db, customer)
    card = await db.scalar(select(CustomerStampCard).where(CustomerStampCard.customer_id == customer.id, CustomerStampCard.stamp_program_id == program.id).with_for_update())
    if not card or not card.is_active or program.is_archived:
        raise HTTPException(409, "برنامج الختم غير موجود داخل بطاقة هذا العميل")
    before = card.stamps
    rewards_before = card.rewards_available
    raw_total = card.stamps + payload.quantity
    earned = raw_total // program.required_stamps
    card.stamps = raw_total % program.required_stamps
    card.rewards_available += earned
    card.lifetime_stamps += payload.quantity
    card.last_stamp_at = datetime.now(timezone.utc)
    customer.visits += 1
    customer.last_visit_at = card.last_stamp_at
    await sync_customer_totals(db, customer)
    tx = StampTransaction(
        brand_id=customer.brand_id, branch_id=branch_id, customer_id=customer.id,
        stamp_program_id=program.id, actor_id=user.id, action="add", delta_stamps=payload.quantity,
        stamps_before=before, stamps_after=card.stamps, delta_rewards=earned,
        rewards_before=rewards_before, rewards_after=card.rewards_available,
        idempotency_key=payload.idempotency_key, reference=payload.reference, note=payload.note,
    )
    db.add(tx)
    wallet_passes = await mark_wallet_updates(db, customer.id)
    add_audit(db, actor_id=user.id, action="stamp_added", entity_type="customer_stamp_card", entity_id=card.id, brand_id=customer.brand_id, details={"customer_id": str(customer.id), "program_id": str(program.id), "quantity": payload.quantity, "earned_rewards": earned}, ip_address=request.client.host if request.client else None)
    await db.commit()
    for wallet_pass in wallet_passes:
        await push_pass_update(db, wallet_pass)
    if wallet_passes:
        await db.commit()
    template, cards = await customer_template_cards(db, customer)
    return {"duplicate": False, "earned_rewards": earned, "customer": {"id": str(customer.id), "name": customer.name, "membership_code": customer.membership_code}, "card_template": {"id": str(template.id), "name": template.name}, "cards": [card_out(c, p) for c, p in cards]}


@router.post("/customers/{customer_id}/programs/{program_id}/redeem")
async def redeem_stamp_reward(customer_id: uuid.UUID, program_id: uuid.UUID, payload: StampRedeem, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    previous = await db.scalar(select(StampTransaction).where(StampTransaction.idempotency_key == payload.idempotency_key))
    if previous:
        return {"duplicate": True}
    customer = await db.scalar(select(Customer).where(Customer.id == customer_id).with_for_update())
    program = await db.get(StampProgram, program_id)
    if not customer or not program or customer.brand_id != program.brand_id:
        raise HTTPException(404, "العميل أو بطاقة الأختام غير موجودة")
    access = await brand_access(db, user, customer.brand_id, permission="rewards.redeem")
    branch_id = operational_branch(access, payload.branch_id)
    await ensure_branch(db, branch_id, customer.brand_id)
    await ensure_customer_cards(db, customer)
    card = await db.scalar(select(CustomerStampCard).where(CustomerStampCard.customer_id == customer.id, CustomerStampCard.stamp_program_id == program.id).with_for_update())
    if not card or card.rewards_available <= 0:
        raise HTTPException(400, "لا توجد مكافأة جاهزة في هذه البطاقة")
    rewards_before = card.rewards_available
    card.rewards_available -= 1
    await sync_customer_totals(db, customer)
    tx = StampTransaction(
        brand_id=customer.brand_id, branch_id=branch_id, customer_id=customer.id,
        stamp_program_id=program.id, actor_id=user.id, action="redeem", delta_stamps=0,
        stamps_before=card.stamps, stamps_after=card.stamps, delta_rewards=-1,
        rewards_before=rewards_before, rewards_after=card.rewards_available,
        idempotency_key=payload.idempotency_key, note=payload.note,
    )
    db.add(tx)
    wallet_passes = await mark_wallet_updates(db, customer.id)
    add_audit(db, actor_id=user.id, action="stamp_reward_redeemed", entity_type="customer_stamp_card", entity_id=card.id, brand_id=customer.brand_id, details={"customer_id": str(customer.id), "program_id": str(program.id), "reward_title": program.reward_title}, ip_address=request.client.host if request.client else None)
    await db.commit()
    for wallet_pass in wallet_passes:
        await push_pass_update(db, wallet_pass)
    if wallet_passes:
        await db.commit()
    template, cards = await customer_template_cards(db, customer)
    return {"duplicate": False, "reward_title": program.reward_title, "card_template": {"id": str(template.id), "name": template.name}, "cards": [card_out(c, p) for c, p in cards]}


def transaction_out(tx: StampTransaction) -> dict:
    return {
        "id": str(tx.id), "brand_id": str(tx.brand_id), "branch_id": str(tx.branch_id) if tx.branch_id else None,
        "customer_id": str(tx.customer_id), "stamp_program_id": str(tx.stamp_program_id),
        "actor_id": str(tx.actor_id) if tx.actor_id else None, "action": tx.action,
        "delta_stamps": tx.delta_stamps, "stamps_before": tx.stamps_before, "stamps_after": tx.stamps_after,
        "delta_rewards": tx.delta_rewards, "rewards_before": tx.rewards_before, "rewards_after": tx.rewards_after,
        "reference": tx.reference, "note": tx.note, "created_at": tx.created_at,
        "reversed_at": tx.reversed_at, "reversal_reason": tx.reversal_reason,
        "original_transaction_id": str(tx.original_transaction_id) if tx.original_transaction_id else None,
        "reversal_transaction_id": str(tx.reversal_transaction_id) if tx.reversal_transaction_id else None,
    }


@router.get("/transactions")
async def list_stamp_transactions(brand_id: uuid.UUID, customer_id: uuid.UUID | None = None, limit: int = 100, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, brand_id, permission="loyalty.apply" if customer_id else "loyalty.view")
    query = select(StampTransaction).where(StampTransaction.brand_id == brand_id)
    if customer_id:
        query = query.where(StampTransaction.customer_id == customer_id)
    rows = list((await db.scalars(query.order_by(StampTransaction.created_at.desc()).limit(min(max(limit, 1), 300)))).all())
    return [transaction_out(row) for row in rows]


@router.post("/transactions/{transaction_id}/reverse")
async def reverse_stamp_transaction(transaction_id: uuid.UUID, payload: StampTransactionReverse, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    duplicate = await db.scalar(select(StampTransaction).where(StampTransaction.idempotency_key == payload.idempotency_key))
    if duplicate:
        return {"duplicate": True, "transaction": transaction_out(duplicate)}
    original = await db.scalar(select(StampTransaction).where(StampTransaction.id == transaction_id).with_for_update())
    if not original:
        raise HTTPException(404, "عملية الختم غير موجودة")
    await brand_access(db, user, original.brand_id, permission="loyalty.reverse")
    if original.action == "reversal" or original.original_transaction_id:
        raise HTTPException(409, "لا يمكن عكس عملية تراجع")
    if original.reversed_at or original.reversal_transaction_id:
        raise HTTPException(409, "تم التراجع عن هذه العملية مسبقًا")
    customer = await db.scalar(select(Customer).where(Customer.id == original.customer_id).with_for_update())
    program = await db.get(StampProgram, original.stamp_program_id)
    card = await db.scalar(select(CustomerStampCard).where(
        CustomerStampCard.customer_id == original.customer_id,
        CustomerStampCard.stamp_program_id == original.stamp_program_id,
    ).with_for_update())
    if not customer or not program or not card:
        raise HTTPException(409, "تعذر استرجاع حالة البطاقة لهذه العملية")
    latest = await db.scalar(
        select(StampTransaction).where(
            StampTransaction.customer_id == original.customer_id,
            StampTransaction.stamp_program_id == original.stamp_program_id,
            StampTransaction.action != "reversal",
            StampTransaction.reversed_at.is_(None),
        ).order_by(StampTransaction.created_at.desc(), StampTransaction.id.desc()).limit(1)
    )
    if not latest or latest.id != original.id:
        raise HTTPException(409, "يمكن التراجع عن آخر عملية فقط حتى يبقى سجل الأختام صحيحًا")
    stamps_before = card.stamps
    rewards_before = card.rewards_available
    if card.stamps != original.stamps_after or card.rewards_available != original.rewards_after:
        raise HTTPException(409, "تغير رصيد البطاقة بعد العملية؛ حدّث الصفحة وتراجع عن آخر عملية أولًا")
    if original.action == "add":
        card.stamps = original.stamps_before
        card.rewards_available = original.rewards_before
        card.lifetime_stamps = max(0, card.lifetime_stamps - max(0, original.delta_stamps))
        customer.visits = max(0, customer.visits - 1)
        previous_add = await db.scalar(
            select(StampTransaction).where(
                StampTransaction.customer_id == original.customer_id,
                StampTransaction.stamp_program_id == original.stamp_program_id,
                StampTransaction.action == "add",
                StampTransaction.id != original.id,
                StampTransaction.reversed_at.is_(None),
            ).order_by(StampTransaction.created_at.desc()).limit(1)
        )
        card.last_stamp_at = previous_add.created_at if previous_add else None
    elif original.action == "redeem":
        card.stamps = original.stamps_before
        card.rewards_available = original.rewards_before
    else:
        raise HTTPException(409, "نوع العملية لا يدعم التراجع")
    await sync_customer_totals(db, customer)
    active_last_dates = list((await db.scalars(
        select(CustomerStampCard.last_stamp_at).where(
            CustomerStampCard.customer_id == customer.id,
            CustomerStampCard.is_active.is_(True),
            CustomerStampCard.last_stamp_at.is_not(None),
        )
    )).all())
    customer.last_visit_at = max(active_last_dates) if active_last_dates else None
    reversal = StampTransaction(
        brand_id=original.brand_id, branch_id=original.branch_id, customer_id=original.customer_id,
        stamp_program_id=original.stamp_program_id, actor_id=user.id, action="reversal",
        delta_stamps=card.stamps - stamps_before, stamps_before=stamps_before, stamps_after=card.stamps,
        delta_rewards=card.rewards_available - rewards_before, rewards_before=rewards_before, rewards_after=card.rewards_available,
        idempotency_key=payload.idempotency_key, note=payload.reason, original_transaction_id=original.id,
    )
    db.add(reversal)
    await db.flush()
    original.reversed_at = datetime.now(timezone.utc)
    original.reversed_by_actor_id = user.id
    original.reversal_reason = payload.reason
    original.reversal_transaction_id = reversal.id
    wallet_passes = await mark_wallet_updates(db, customer.id)
    add_audit(db, actor_id=user.id, action="stamp_transaction_reversed", entity_type="stamp_transaction", entity_id=original.id, brand_id=original.brand_id, details={"reversal_id": str(reversal.id), "reason": payload.reason}, ip_address=request.client.host if request.client else None)
    await db.commit()
    for wallet_pass in wallet_passes:
        await push_pass_update(db, wallet_pass)
    if wallet_passes:
        await db.commit()
    template, cards = await customer_template_cards(db, customer)
    return {"duplicate": False, "transaction": transaction_out(reversal), "card_template": {"id": str(template.id), "name": template.name}, "cards": [card_out(c, p) for c, p in cards]}
