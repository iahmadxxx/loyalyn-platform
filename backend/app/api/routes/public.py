from __future__ import annotations

import secrets
from io import BytesIO

import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.stamps import card_out, ensure_customer_cards, program_out
from app.core.config import get_settings
from app.db.session import get_db
from app.models import Brand, BrandWalletDesign, Customer, StampProgram, WalletPass
from app.schemas.common import PublicJoin
from app.services.capabilities import brand_capabilities
from app.services.wallet import active_credential

router = APIRouter()
settings = get_settings()


def public_program(program: StampProgram) -> dict:
    data = program_out(program)
    data.update({
        "card_asset_url": f"{settings.public_api_url.rstrip('/')}/api/stamps/public/assets/{program.id}/card" if program.card_image_url else None,
        "empty_stamp_asset_url": f"{settings.public_api_url.rstrip('/')}/api/stamps/public/assets/{program.id}/empty_stamp" if program.empty_stamp_image_url else None,
        "filled_stamp_asset_url": f"{settings.public_api_url.rstrip('/')}/api/stamps/public/assets/{program.id}/filled_stamp" if program.filled_stamp_image_url else None,
    })
    for key in ("card_image_url", "empty_stamp_image_url", "filled_stamp_image_url"):
        data.pop(key, None)
    return data


async def public_brand(db: AsyncSession, slug: str) -> Brand:
    brand = await db.scalar(select(Brand).where(Brand.slug == slug.strip().lower(), Brand.is_active.is_(True)))
    if not brand or not brand.join_enabled:
        raise HTTPException(404, "صفحة التسجيل غير متاحة")
    return brand


@router.get("/brands/{slug}")
async def brand_join_profile(slug: str, db: AsyncSession = Depends(get_db)):
    brand = await public_brand(db, slug)
    programs = list((await db.scalars(
        select(StampProgram).where(StampProgram.brand_id == brand.id, StampProgram.is_active.is_(True))
        .order_by(StampProgram.sort_order, StampProgram.created_at)
    )).all())
    join_url = f"{settings.public_web_url.rstrip('/')}/join/{brand.slug}"
    return {
        "brand": {
            "id": str(brand.id), "name": brand.name, "slug": brand.slug, "logo_url": brand.logo_url,
            "primary_color": brand.primary_color, "accent_color": brand.accent_color,
            "program_mode": brand.program_mode, "capabilities": brand_capabilities(brand),
            "join_require_email": brand.join_require_email,
            "join_welcome_text": brand.join_welcome_text or "سجّل بياناتك وأضف بطاقة البراند بسهولة.",
        },
        "programs": [public_program(x) for x in programs],
        "join_url": join_url,
        "qr_url": f"{settings.public_api_url.rstrip('/')}/api/public/brands/{brand.slug}/join-qr.svg",
    }


@router.get("/brands/{slug}/join-qr.svg")
async def brand_join_qr(slug: str, db: AsyncSession = Depends(get_db)):
    brand = await public_brand(db, slug)
    value = f"{settings.public_web_url.rstrip('/')}/join/{brand.slug}"
    image = qrcode.make(value, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    buffer = BytesIO()
    image.save(buffer)
    return Response(buffer.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


@router.get("/members/{membership_code}/qr.svg")
async def member_qr(membership_code: str, db: AsyncSession = Depends(get_db)):
    customer = await db.scalar(select(Customer).where(Customer.membership_code == membership_code, Customer.is_active.is_(True)))
    if not customer:
        raise HTTPException(404, "العضوية غير موجودة")
    image = qrcode.make(customer.membership_code, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    buffer = BytesIO()
    image.save(buffer)
    return Response(buffer.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "private, max-age=3600"})


@router.post("/brands/{slug}/join", status_code=201)
async def join_brand(slug: str, payload: PublicJoin, db: AsyncSession = Depends(get_db)):
    brand = await public_brand(db, slug)
    if brand.join_require_email and not payload.email:
        raise HTTPException(422, "البريد الإلكتروني مطلوب للتسجيل في هذا البراند")
    customer = await db.scalar(select(Customer).where(Customer.brand_id == brand.id, Customer.phone == payload.phone))
    created = customer is None
    if not customer:
        customer = Customer(
            brand_id=brand.id, name=payload.name, phone=payload.phone, email=payload.email,
            birthday=payload.birthday, membership_code=secrets.token_urlsafe(18), tags=[],
        )
        db.add(customer)
        await db.flush()
    else:
        customer.name = payload.name or customer.name
        if payload.email:
            customer.email = payload.email
        if payload.birthday:
            customer.birthday = payload.birthday
        customer.is_active = True
    cards = await ensure_customer_cards(db, customer)
    selected = {str(x) for x in payload.selected_program_ids}
    if selected:
        for card, program in cards:
            card.is_active = str(program.id) in selected
    # Create a stable Wallet pass record when the platform is ready. Download/signing remains lazy.
    design = await db.scalar(select(BrandWalletDesign).where(BrandWalletDesign.brand_id == brand.id))
    credential = await active_credential(db)
    wallet_pass = await db.scalar(select(WalletPass).where(WalletPass.brand_id == brand.id, WalletPass.customer_id == customer.id))
    wallet_ready = bool(design and design.is_published and credential)
    if wallet_ready and not wallet_pass:
        wallet_pass = WalletPass(
            brand_id=brand.id, customer_id=customer.id,
            serial_number=secrets.token_urlsafe(18), public_token=secrets.token_urlsafe(28),
            authentication_token=secrets.token_urlsafe(32), pass_type_identifier=credential.pass_type_identifier,
            update_tag=1,
        )
        db.add(wallet_pass)
        await db.flush()
    await db.commit()
    active_cards = [card_out(card, program) for card, program in cards if card.is_active]
    result = {
        "created": created,
        "customer": {"id": str(customer.id), "name": customer.name, "membership_code": customer.membership_code},
        "cards": active_cards,
        "scan_code": customer.membership_code,
        "wallet_ready": wallet_ready,
        "card_url": None,
        "download_url": None,
    }
    if wallet_ready and wallet_pass:
        result["card_url"] = f"{settings.public_web_url.rstrip('/')}/card/{wallet_pass.public_token}"
        result["download_url"] = f"{settings.public_api_url.rstrip('/')}/api/wallet/public/{wallet_pass.public_token}.pkpass"
    return result
