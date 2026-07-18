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
from app.models import Brand, BrandWalletDesign, CardTemplate, Customer, StampProgram, WalletPass
from app.schemas.common import PublicJoin
from app.services.capabilities import brand_capabilities
from app.services.cards import assign_template, ensure_default_template, template_out
from app.services.wallet import active_credential, public_wallet_status

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
    default_template = await ensure_default_template(db, brand)
    templates = list((await db.scalars(
        select(CardTemplate).where(
            CardTemplate.brand_id == brand.id,
            CardTemplate.status == "published",
            CardTemplate.allow_public_join.is_(True),
        ).order_by(CardTemplate.is_default.desc(), CardTemplate.sort_order, CardTemplate.created_at)
    )).all())
    if default_template not in templates and default_template.status == "published" and default_template.allow_public_join:
        templates.insert(0, default_template)
    await db.commit()
    template_payloads = [await template_out(db, template, include_usage=False, published_view=True) for template in templates]
    programs = list((await db.scalars(
        select(StampProgram).where(
            StampProgram.brand_id == brand.id,
            StampProgram.is_active.is_(True),
            StampProgram.is_archived.is_(False),
        ).order_by(StampProgram.sort_order, StampProgram.created_at)
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
        "card_templates": template_payloads,
        "default_card_template_id": str(default_template.id),
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
    # Preserve the zero-setup enrollment flow for new and upgraded brands:
    # when no explicit card exists yet, create a published main card from the
    # active stamp programs. Managers can later edit, duplicate or replace it.
    await ensure_default_template(db, brand)
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

    # V6 single-brand studio uses registration first, then the manager chooses
    # one or several cards for the customer. Older clients that explicitly
    # send a card (or the legacy selected_program_ids field) keep the original
    # self-service issue flow.
    self_service_issue = bool(payload.selected_card_template_id) or "selected_program_ids" in payload.model_fields_set
    if not self_service_issue:
        cards = await ensure_customer_cards(db, customer)
        await db.commit()
        wallet = {
            "ready": False,
            "status": "assignment_pending",
            "message": "تم تسجيل عضويتك. سيحدد البراند البطاقة أو البطاقات المناسبة لك ثم يرسل روابط إضافتها إلى Apple Wallet.",
            "card_url": None,
            "download_url": None,
        }
        return {
            "created": created,
            "customer": {"id": str(customer.id), "name": customer.name, "membership_code": customer.membership_code},
            "cards": [card_out(card, program) for card, program in cards if card.is_active],
            "card_template": None,
            "scan_code": customer.membership_code,
            "wallet": wallet,
            "wallet_ready": False,
            "card_url": None,
            "download_url": None,
        }

    template = None
    if payload.selected_card_template_id:
        template = await db.get(CardTemplate, payload.selected_card_template_id)
        if not template or template.brand_id != brand.id or template.status != "published" or not template.allow_public_join:
            raise HTTPException(422, "البطاقة المختارة غير متاحة أو لم تُنشر بعد")
    if not template:
        template = await db.scalar(
            select(CardTemplate).where(
                CardTemplate.brand_id == brand.id,
                CardTemplate.status == "published",
                CardTemplate.allow_public_join.is_(True),
            ).order_by(CardTemplate.is_default.desc(), CardTemplate.sort_order, CardTemplate.created_at)
        )
    if not template:
        raise HTTPException(409, "لا توجد بطاقة منشورة ومتاحة للتسجيل حاليًا")
    await assign_template(db, customer, template)
    cards = await ensure_customer_cards(db, customer)
    # Keep a stable public card page for every Wallet-enabled membership, even
    # when the platform certificate or published design is not ready yet.
    # This lets the same customer link become downloadable later without
    # creating a second membership or confusing the membership QR with a pass.
    design = await db.scalar(select(BrandWalletDesign).where(BrandWalletDesign.brand_id == brand.id))
    credential = await active_credential(db)
    wallet = public_wallet_status(brand=brand, design=design, credential=credential, card_template=template)
    wallet_pass = await db.scalar(select(WalletPass).where(
        WalletPass.brand_id == brand.id, WalletPass.customer_id == customer.id,
        WalletPass.card_template_id == template.id,
    ))
    if brand_capabilities(brand).get("wallet"):
        if not wallet_pass:
            wallet_pass = WalletPass(
                brand_id=brand.id, customer_id=customer.id, card_template_id=template.id,
                serial_number=secrets.token_urlsafe(18), public_token=secrets.token_urlsafe(28),
                authentication_token=secrets.token_urlsafe(32),
                pass_type_identifier=credential.pass_type_identifier if credential else None,
                update_tag=1,
            )
            db.add(wallet_pass)
            await db.flush()
        else:
            wallet_pass.status = "active"
            wallet_pass.card_template_id = template.id
            if credential:
                wallet_pass.pass_type_identifier = credential.pass_type_identifier
    await db.commit()
    active_cards = [card_out(card, program) for card, program in cards if card.is_active]
    card_url = f"{settings.public_web_url.rstrip('/')}/card/{wallet_pass.public_token}" if wallet_pass else None
    download_url = (
        f"{settings.public_api_url.rstrip('/')}/api/wallet/public/{wallet_pass.public_token}.pkpass"
        if wallet_pass and wallet["ready"] else None
    )
    wallet.update({"card_url": card_url, "download_url": download_url})
    return {
        "created": created,
        "customer": {"id": str(customer.id), "name": customer.name, "membership_code": customer.membership_code},
        "cards": active_cards,
        "card_template": await template_out(db, template, include_usage=False, published_view=True),
        "scan_code": customer.membership_code,
        "wallet": wallet,
        # Backward-compatible fields for older frontend builds.
        "wallet_ready": wallet["ready"],
        "card_url": card_url,
        "download_url": download_url,
    }
