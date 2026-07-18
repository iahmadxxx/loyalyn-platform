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
    Brand, Branch, Customer, CustomerStampCard, StampProgram, StampTransaction, WalletPass,
)
from app.schemas.common import StampAction, StampProgramCreate, StampProgramUpdate, StampRedeem
from app.services.audit import add_audit
from app.services.capabilities import brand_capabilities
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
        "card_image_url": program.card_image_url,
        "empty_stamp_image_url": program.empty_stamp_image_url,
        "filled_stamp_image_url": program.filled_stamp_image_url,
        "is_default": program.is_default, "sort_order": program.sort_order,
        "is_active": program.is_active, "created_at": program.created_at, "updated_at": program.updated_at,
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
    programs = list((await db.scalars(
        select(StampProgram).where(StampProgram.brand_id == customer.brand_id, StampProgram.is_active.is_(True))
        .order_by(StampProgram.sort_order, StampProgram.created_at)
    )).all())
    existing = {x.stamp_program_id: x for x in (await db.scalars(
        select(CustomerStampCard).where(CustomerStampCard.customer_id == customer.id)
    )).all()}
    had_any = bool(existing)
    result: list[tuple[CustomerStampCard, StampProgram]] = []
    default_consumed = False
    for program in programs:
        card = existing.get(program.id)
        if not card:
            migrate_legacy = not had_any and not default_consumed and (program.is_default or program == programs[0])
            card = CustomerStampCard(
                brand_id=customer.brand_id, customer_id=customer.id, stamp_program_id=program.id,
                stamps=customer.stamps if migrate_legacy else 0,
                rewards_available=customer.available_rewards if migrate_legacy else 0,
                lifetime_stamps=customer.stamps if migrate_legacy else 0,
                is_active=True,
            )
            db.add(card)
            await db.flush()
            if migrate_legacy:
                default_consumed = True
        result.append((card, program))
    return result


async def sync_customer_totals(db: AsyncSession, customer: Customer) -> None:
    totals = (await db.execute(
        select(
            func.coalesce(func.sum(CustomerStampCard.stamps), 0),
            func.coalesce(func.sum(CustomerStampCard.rewards_available), 0),
        ).where(CustomerStampCard.customer_id == customer.id, CustomerStampCard.is_active.is_(True))
    )).one()
    customer.stamps = int(totals[0] or 0)
    customer.available_rewards = int(totals[1] or 0)


async def mark_wallet_update(db: AsyncSession, customer_id: uuid.UUID) -> WalletPass | None:
    wallet_pass = await db.scalar(select(WalletPass).where(WalletPass.customer_id == customer_id, WalletPass.status == "active"))
    if wallet_pass:
        wallet_pass.update_tag += 1
    return wallet_pass


@router.get("/programs")
async def list_programs(brand_id: uuid.UUID, active_only: bool = False, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, brand_id, permission="loyalty.view")
    await require_stamps(db, brand_id)
    query = select(StampProgram).where(StampProgram.brand_id == brand_id)
    if active_only:
        query = query.where(StampProgram.is_active.is_(True))
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
    cards = await ensure_customer_cards(db, customer)
    await db.commit()
    return {
        "brand": {"id": str(brand.id), "name": brand.name, "slug": brand.slug},
        "customer": {"id": str(customer.id), "name": customer.name, "phone": customer.phone, "membership_code": customer.membership_code, "last_visit_at": customer.last_visit_at},
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
    wallet_pass = await mark_wallet_update(db, customer.id)
    add_audit(db, actor_id=user.id, action="stamp_added", entity_type="customer_stamp_card", entity_id=card.id, brand_id=customer.brand_id, details={"customer_id": str(customer.id), "program_id": str(program.id), "quantity": payload.quantity, "earned_rewards": earned}, ip_address=request.client.host if request.client else None)
    await db.commit()
    if wallet_pass:
        await push_pass_update(db, wallet_pass)
        await db.commit()
    cards = await ensure_customer_cards(db, customer)
    return {"duplicate": False, "earned_rewards": earned, "customer": {"id": str(customer.id), "name": customer.name, "membership_code": customer.membership_code}, "cards": [card_out(c, p) for c, p in cards]}


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
    wallet_pass = await mark_wallet_update(db, customer.id)
    add_audit(db, actor_id=user.id, action="stamp_reward_redeemed", entity_type="customer_stamp_card", entity_id=card.id, brand_id=customer.brand_id, details={"customer_id": str(customer.id), "program_id": str(program.id), "reward_title": program.reward_title}, ip_address=request.client.host if request.client else None)
    await db.commit()
    if wallet_pass:
        await push_pass_update(db, wallet_pass)
        await db.commit()
    cards = await ensure_customer_cards(db, customer)
    return {"duplicate": False, "reward_title": program.reward_title, "cards": [card_out(c, p) for c, p in cards]}
