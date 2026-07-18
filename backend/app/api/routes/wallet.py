import secrets
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import brand_access, current_user, require_platform_owner
from app.core.config import get_settings
from app.core.security import encrypt_secret
from app.db.session import get_db
from app.models import (
    Brand, BrandWalletDesign, CardTemplate, Customer, CustomerStampCard, PlatformWalletCredential, StampProgram, WalletDevice,
    WalletPass, WalletRegistration,
)
from app.schemas.common import WalletDesignUpdate, WalletPushToken
from app.services.audit import add_audit
from app.services.capabilities import brand_capabilities
from app.services.cards import active_template_for_customer, attach_template, customer_template_cards, published_design, template_out
from app.services.wallet import active_credential, generate_pkpass_bytes, public_wallet_status, validate_and_extract_certificate

router = APIRouter()
settings = get_settings()


async def require_wallet_feature(db: AsyncSession, brand_id: uuid.UUID) -> Brand:
    brand = await db.get(Brand, brand_id)
    if not brand or not brand.is_active:
        raise HTTPException(404, "البراند غير موجود أو موقوف")
    if not brand_capabilities(brand).get("wallet"):
        raise HTTPException(409, "ميزة Apple Wallet غير مفعلة لهذا البراند")
    return brand


def credential_out(x: PlatformWalletCredential | None) -> dict:
    if not x:
        return {"configured": False, "status": "not_configured"}
    return {
        "configured": True, "id": str(x.id), "filename": x.filename,
        "pass_type_identifier": x.pass_type_identifier, "team_identifier": x.team_identifier,
        "organization_name": x.organization_name, "certificate_subject": x.certificate_subject,
        "expires_at": x.expires_at, "status": x.status, "is_active": x.is_active,
        "created_at": x.created_at,
    }


def design_out(x: BrandWalletDesign) -> dict:
    return {
        "id": str(x.id), "brand_id": str(x.brand_id), "background_color": x.background_color,
        "foreground_color": x.foreground_color, "label_color": x.label_color,
        "logo_text": x.logo_text, "card_title": x.card_title, "logo_url": x.logo_url,
        "hero_url": x.hero_url, "background_image_url": x.background_image_url,
        "strip_url": x.strip_url, "layout_style": x.layout_style, "overlay_opacity": x.overlay_opacity,
        "barcode_format": x.barcode_format, "fields": x.fields or {},
        "terms": x.terms, "draft_version": x.draft_version, "published_version": x.published_version,
        "is_published": x.is_published, "updated_at": x.updated_at,
    }


async def ensure_design(db: AsyncSession, brand: Brand) -> BrandWalletDesign:
    design = await db.scalar(select(BrandWalletDesign).where(BrandWalletDesign.brand_id == brand.id))
    if not design:
        design = BrandWalletDesign(
            brand_id=brand.id, background_color=brand.primary_color, label_color=brand.accent_color,
            logo_text=brand.name, fields={"show_points": True, "show_stamps": True, "show_rewards": True, "show_tier": True, "show_visits": True},
        )
        db.add(design)
        await db.commit()
        await db.refresh(design)
    return design


async def pass_entities(db: AsyncSession, wallet_pass: WalletPass):
    customer = await db.get(Customer, wallet_pass.customer_id)
    brand = await db.get(Brand, wallet_pass.brand_id)
    if not customer or not brand:
        raise HTTPException(404, "البطاقة أو العميل غير موجود")
    template = await db.get(CardTemplate, wallet_pass.card_template_id) if wallet_pass.card_template_id else None
    if not template or template.brand_id != brand.id or template.status == "archived":
        _, template = await active_template_for_customer(db, customer)
        wallet_pass.card_template_id = template.id
    template, stamp_rows = await customer_template_cards(db, customer, template)
    customer._wallet_stamp_cards = [
        {
            "id": str(program.id), "name": program.name, "stamps": card.stamps,
            "required_stamps": program.required_stamps, "rewards_available": card.rewards_available,
            "reward_title": program.reward_title, "stamp_icon": program.stamp_icon,
            "empty_stamp_image_url": program.empty_stamp_image_url,
            "filled_stamp_image_url": program.filled_stamp_image_url,
            "display_options": dict(program.display_options or {}),
            "accent_color": program.accent_color, "background_color": program.background_color,
        } for card, program in stamp_rows
    ]
    credential = await active_credential(db)
    if not credential:
        raise HTTPException(503, "شهادة Apple Wallet المركزية غير مهيأة")
    if template.status != "published":
        raise HTTPException(409, "يجب نشر البطاقة المختارة قبل الإصدار")
    if wallet_pass.pass_type_identifier != credential.pass_type_identifier:
        wallet_pass.pass_type_identifier = credential.pass_type_identifier
    return credential, brand, customer, published_design(template)


def check_apple_auth(header: str | None, wallet_pass: WalletPass) -> None:
    expected = f"ApplePass {wallet_pass.authentication_token}"
    if not header or not secrets.compare_digest(header, expected):
        raise HTTPException(401, "Unauthorized")


@router.get("/platform/credential")
async def get_platform_credential(db: AsyncSession = Depends(get_db), user=Depends(require_platform_owner)):
    return credential_out(await active_credential(db))


@router.post("/platform/credential", status_code=201)
async def upload_platform_credential(
    request: Request,
    p12_file: UploadFile = File(...),
    wwdr_file: UploadFile = File(...),
    password: str = Form(...),
    pass_type_identifier: str = Form(...),
    team_identifier: str = Form(...),
    organization_name: str = Form("Loyalyn"),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_platform_owner),
):
    if not p12_file.filename or not p12_file.filename.lower().endswith(".p12"):
        raise HTTPException(400, "ملف الشهادة يجب أن يكون بصيغة .p12")
    if not wwdr_file.filename or not wwdr_file.filename.lower().endswith((".cer", ".pem")):
        raise HTTPException(400, "ملف WWDR يجب أن يكون بصيغة .cer أو .pem")
    if not pass_type_identifier.startswith("pass."):
        raise HTTPException(400, "Pass Type Identifier يجب أن يبدأ بـ pass.")
    credential_id = uuid.uuid4()
    folder = settings.wallet_path / "credentials" / str(credential_id)
    folder.mkdir(parents=True, exist_ok=True)
    p12_path = folder / "certificate.p12"
    wwdr_source = folder / f"wwdr-source{Path(wwdr_file.filename).suffix.lower()}"
    p12_data = await p12_file.read()
    wwdr_data = await wwdr_file.read()
    if len(p12_data) > 5 * 1024 * 1024 or len(wwdr_data) > 5 * 1024 * 1024:
        shutil.rmtree(folder, ignore_errors=True)
        raise HTTPException(413, "حجم ملف الشهادة أكبر من الحد المسموح")
    p12_path.write_bytes(p12_data)
    wwdr_source.write_bytes(wwdr_data)
    try:
        metadata = validate_and_extract_certificate(
            p12_path,
            wwdr_source,
            password,
            folder,
            expected_pass_type_identifier=pass_type_identifier.strip(),
            expected_team_identifier=team_identifier.strip(),
        )
    except Exception as exc:
        shutil.rmtree(folder, ignore_errors=True)
        raise HTTPException(400, f"تعذر التحقق من الشهادة: {str(exc)}") from exc
    previous = list((await db.scalars(select(PlatformWalletCredential).where(PlatformWalletCredential.is_active.is_(True)))).all())
    for item in previous:
        item.is_active = False
        item.status = "replaced"
    credential = PlatformWalletCredential(
        id=credential_id,
        filename=p12_file.filename,
        p12_path=str(p12_path),
        wwdr_path=metadata["wwdr_path"],
        encrypted_password=encrypt_secret(password),
        pass_type_identifier=pass_type_identifier.strip(),
        team_identifier=team_identifier.strip(),
        organization_name=organization_name.strip() or "Loyalyn",
        certificate_subject=metadata["certificate_subject"],
        expires_at=metadata["expires_at"],
        status="active",
        is_active=True,
    )
    db.add(credential)
    add_audit(db, actor_id=user.id, action="wallet_credential_uploaded", entity_type="platform_wallet_credential", entity_id=credential.id, details={"filename": credential.filename, "pass_type_identifier": credential.pass_type_identifier, "expires_at": credential.expires_at.isoformat()}, ip_address=request.client.host if request.client else None)
    await db.commit()
    await db.refresh(credential)
    return credential_out(credential)


@router.post("/design/{brand_id}/asset")
async def upload_design_asset(
    brand_id: uuid.UUID,
    kind: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(current_user),
):
    await brand_access(db, user, brand_id, permission="wallet.design")
    await require_wallet_feature(db, brand_id)
    if kind not in {"logo", "hero", "background", "strip"}:
        raise HTTPException(400, "نوع الأصل غير صحيح")
    if not file.filename or not file.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        raise HTTPException(400, "الصورة يجب أن تكون PNG أو JPG أو WebP")
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "حجم الصورة أكبر من 5MB")
    brand = await db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(404, "البراند غير موجود")
    folder = settings.wallet_path / "brands" / str(brand_id)
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
    design = await ensure_design(db, brand)
    value = f"storage://{destination}"
    if kind == "logo":
        design.logo_url = value
    elif kind == "hero":
        design.hero_url = value
    elif kind == "background":
        design.background_image_url = value
    else:
        design.strip_url = value
    design.draft_version += 1
    await db.commit()
    return {"ok": True, "kind": kind, "preview_url": f"{settings.public_api_url.rstrip('/')}/api/wallet/public/assets/{brand_id}/{kind}"}


@router.get("/public/assets/{brand_id}/{kind}")
async def public_design_asset(brand_id: uuid.UUID, kind: str, db: AsyncSession = Depends(get_db)):
    if kind not in {"logo", "hero", "background", "strip"}:
        raise HTTPException(404, "Asset not found")
    design = await db.scalar(select(BrandWalletDesign).where(BrandWalletDesign.brand_id == brand_id))
    source = None
    if design:
        source = {
            "logo": design.logo_url, "hero": design.hero_url,
            "background": design.background_image_url, "strip": design.strip_url,
        }.get(kind)
    if not source or not source.startswith("storage://"):
        raise HTTPException(404, "Asset not found")
    path = Path(source.removeprefix("storage://"))
    if not path.exists():
        raise HTTPException(404, "Asset not found")
    return FileResponse(path)


@router.get("/design/{brand_id}")
async def get_design(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, brand_id, permission="wallet.view")
    await require_wallet_feature(db, brand_id)
    brand = await db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(404, "البراند غير موجود")
    return design_out(await ensure_design(db, brand))


@router.put("/design/{brand_id}")
async def update_design(brand_id: uuid.UUID, payload: WalletDesignUpdate, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, brand_id, permission="wallet.design")
    await require_wallet_feature(db, brand_id)
    brand = await db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(404, "البراند غير موجود")
    design = await ensure_design(db, brand)
    for field, value in payload.model_dump().items():
        setattr(design, field, value)
    design.draft_version += 1
    add_audit(db, actor_id=user.id, action="wallet_design_saved", entity_type="wallet_design", entity_id=design.id, brand_id=brand_id, details={"draft_version": design.draft_version}, ip_address=request.client.host if request.client else None)
    await db.commit()
    await db.refresh(design)
    return design_out(design)


@router.post("/design/{brand_id}/publish")
async def publish_design(brand_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, brand_id, permission="wallet.design")
    await require_wallet_feature(db, brand_id)
    brand = await db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(404, "البراند غير موجود")
    if not await active_credential(db):
        raise HTTPException(409, "مدير المنصة لم يرفع شهادة Apple Wallet بعد")
    design = await ensure_design(db, brand)
    design.is_published = True
    design.published_version = design.draft_version
    passes = list((await db.scalars(select(WalletPass).where(WalletPass.brand_id == brand_id, WalletPass.status == "active"))).all())
    for wallet_pass in passes:
        wallet_pass.update_tag += 1
    add_audit(db, actor_id=user.id, action="wallet_design_published", entity_type="wallet_design", entity_id=design.id, brand_id=brand_id, details={"version": design.published_version, "passes_marked_for_update": len(passes)}, ip_address=request.client.host if request.client else None)
    await db.commit()
    await db.refresh(design)
    return design_out(design)


@router.post("/passes/{customer_id}", status_code=201)
async def issue_pass(customer_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(404, "العميل غير موجود")
    await brand_access(db, user, customer.brand_id, permission="wallet.issue")
    await require_wallet_feature(db, customer.brand_id)
    credential = await active_credential(db)
    if not credential:
        raise HTTPException(409, "شهادة Apple Wallet المركزية غير مهيأة")
    brand = await db.get(Brand, customer.brand_id)
    _, template = await active_template_for_customer(db, customer)
    if template.status != "published":
        raise HTTPException(409, "يجب نشر البطاقة المختارة قبل الإصدار")
    wallet_pass = await db.scalar(select(WalletPass).where(
        WalletPass.customer_id == customer.id, WalletPass.brand_id == customer.brand_id,
        WalletPass.card_template_id == template.id,
    ))
    if not wallet_pass:
        wallet_pass = WalletPass(
            brand_id=customer.brand_id, customer_id=customer.id, card_template_id=template.id,
            serial_number=secrets.token_urlsafe(18), public_token=secrets.token_urlsafe(28),
            authentication_token=secrets.token_urlsafe(32), pass_type_identifier=credential.pass_type_identifier,
            update_tag=1,
        )
        db.add(wallet_pass)
        await db.flush()
    else:
        wallet_pass.status = "active"
        wallet_pass.card_template_id = template.id
        wallet_pass.pass_type_identifier = credential.pass_type_identifier
        if not wallet_pass.authentication_token:
            wallet_pass.authentication_token = secrets.token_urlsafe(32)
        if not wallet_pass.public_token:
            wallet_pass.public_token = secrets.token_urlsafe(28)
        wallet_pass.update_tag += 1
    add_audit(db, actor_id=user.id, action="wallet_pass_issued", entity_type="wallet_pass", entity_id=wallet_pass.id, brand_id=customer.brand_id, details={"customer_id": str(customer.id)}, ip_address=request.client.host if request.client else None)
    await db.commit()
    await db.refresh(wallet_pass)
    return {
        "id": str(wallet_pass.id), "serial_number": wallet_pass.serial_number,
        "card_url": f"{settings.public_web_url.rstrip('/')}/card/{wallet_pass.public_token}",
        "download_url": f"{settings.public_api_url.rstrip('/')}/api/wallet/public/{wallet_pass.public_token}.pkpass",
    }



@router.post("/passes/{customer_id}/{template_id}", status_code=201)
async def issue_template_pass(customer_id: uuid.UUID, template_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    customer = await db.get(Customer, customer_id)
    template = await db.get(CardTemplate, template_id)
    if not customer or not template or template.brand_id != customer.brand_id:
        raise HTTPException(404, "العميل أو البطاقة غير موجودة")
    await brand_access(db, user, customer.brand_id, permission="wallet.issue")
    await require_wallet_feature(db, customer.brand_id)
    if template.status != "published":
        raise HTTPException(409, "انشر البطاقة أولًا قبل إصدارها")
    credential = await active_credential(db)
    if not credential:
        raise HTTPException(409, "شهادة Apple Wallet المركزية غير مهيأة")
    await attach_template(db, customer, template, actor_id=user.id)
    wallet_pass = await db.scalar(select(WalletPass).where(
        WalletPass.customer_id == customer.id,
        WalletPass.card_template_id == template.id,
    ))
    if not wallet_pass:
        wallet_pass = WalletPass(
            brand_id=customer.brand_id, customer_id=customer.id, card_template_id=template.id,
            serial_number=secrets.token_urlsafe(18), public_token=secrets.token_urlsafe(28),
            authentication_token=secrets.token_urlsafe(32), pass_type_identifier=credential.pass_type_identifier,
            update_tag=1, status="active",
        )
        db.add(wallet_pass)
        await db.flush()
    else:
        wallet_pass.status = "active"
        wallet_pass.pass_type_identifier = credential.pass_type_identifier
        wallet_pass.update_tag += 1
    add_audit(db, actor_id=user.id, action="wallet_template_pass_issued", entity_type="wallet_pass", entity_id=wallet_pass.id, brand_id=customer.brand_id, details={"customer_id": str(customer.id), "template_id": str(template.id)}, ip_address=request.client.host if request.client else None)
    await db.commit()
    return {
        "id": str(wallet_pass.id), "serial_number": wallet_pass.serial_number,
        "card_template_id": str(template.id), "card_template_name": template.name,
        "card_url": f"{settings.public_web_url.rstrip('/')}/card/{wallet_pass.public_token}",
        "download_url": f"{settings.public_api_url.rstrip('/')}/api/wallet/public/{wallet_pass.public_token}.pkpass",
    }


@router.get("/public/{token}.pkpass")
async def public_pkpass(token: str, db: AsyncSession = Depends(get_db)):
    wallet_pass = await db.scalar(select(WalletPass).where(WalletPass.public_token == token, WalletPass.status == "active"))
    if not wallet_pass:
        raise HTTPException(404, "البطاقة غير موجودة")
    credential, brand, customer, design = await pass_entities(db, wallet_pass)
    try:
        data = generate_pkpass_bytes(credential=credential, brand=brand, customer=customer, design=design, wallet_pass=wallet_pass)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    wallet_pass.last_generated_at = datetime.now(timezone.utc)
    await db.commit()
    return Response(
        data,
        media_type="application/vnd.apple.pkpass",
        headers={
            "Content-Disposition": f'attachment; filename="{brand.slug}-{customer.membership_code}.pkpass"',
            "Content-Transfer-Encoding": "binary",
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/public/card/{token}")
async def public_card(token: str, db: AsyncSession = Depends(get_db)):
    wallet_pass = await db.scalar(select(WalletPass).where(WalletPass.public_token == token, WalletPass.status == "active"))
    if not wallet_pass:
        raise HTTPException(404, "البطاقة غير موجودة")
    customer = await db.get(Customer, wallet_pass.customer_id)
    brand = await db.get(Brand, wallet_pass.brand_id)
    template = await db.get(CardTemplate, wallet_pass.card_template_id) if wallet_pass.card_template_id else None
    if not template or template.brand_id != brand.id or template.status == "archived":
        _, template = await active_template_for_customer(db, customer)
        wallet_pass.card_template_id = template.id
    template, stamp_rows = await customer_template_cards(db, customer, template)
    credential = await active_credential(db)
    fallback_design = await ensure_design(db, brand)
    wallet = public_wallet_status(brand=brand, design=fallback_design, credential=credential, card_template=template)
    download_url = (
        f"{settings.public_api_url.rstrip('/')}/api/wallet/public/{wallet_pass.public_token}.pkpass"
        if wallet["ready"] else None
    )
    wallet.update({
        "card_url": f"{settings.public_web_url.rstrip('/')}/card/{wallet_pass.public_token}",
        "download_url": download_url,
    })
    await db.commit()
    return {
        "brand": {"name": brand.name, "slug": brand.slug, "logo_url": brand.logo_url, "primary_color": brand.primary_color, "accent_color": brand.accent_color, "program_mode": brand.program_mode},
        "customer": {"name": customer.name, "points": customer.points, "stamps": customer.stamps, "rewards": customer.available_rewards, "tier": customer.tier, "membership_code": customer.membership_code},
        "stamp_cards": [{"id": str(program.id), "name": program.name, "stamps": card.stamps, "required_stamps": program.required_stamps, "rewards_available": card.rewards_available, "background_color": program.background_color, "accent_color": program.accent_color, "stamp_icon": program.stamp_icon} for card, program in stamp_rows],
        "card_template": await template_out(db, template, include_usage=False, published_view=True),
        "design": await template_out(db, template, include_usage=False, published_view=True),
        "wallet": wallet,
        "download_url": download_url,
    }


async def find_pass(db: AsyncSession, pass_type_identifier: str, serial_number: str) -> WalletPass:
    wallet_pass = await db.scalar(select(WalletPass).where(WalletPass.pass_type_identifier == pass_type_identifier, WalletPass.serial_number == serial_number, WalletPass.status == "active"))
    if not wallet_pass:
        raise HTTPException(404, "Pass not found")
    return wallet_pass


@router.post("/v1/devices/{device_library_identifier}/registrations/{pass_type_identifier}/{serial_number}")
async def register_pass(device_library_identifier: str, pass_type_identifier: str, serial_number: str, payload: WalletPushToken, authorization: str | None = Header(default=None), db: AsyncSession = Depends(get_db)):
    wallet_pass = await find_pass(db, pass_type_identifier, serial_number)
    check_apple_auth(authorization, wallet_pass)
    device = await db.scalar(select(WalletDevice).where(WalletDevice.device_library_identifier == device_library_identifier))
    if not device:
        device = WalletDevice(device_library_identifier=device_library_identifier, push_token=payload.pushToken, is_active=True)
        db.add(device)
        await db.flush()
    else:
        device.push_token = payload.pushToken
        device.is_active = True
    registration = await db.scalar(select(WalletRegistration).where(WalletRegistration.device_id == device.id, WalletRegistration.pass_id == wallet_pass.id))
    created = registration is None
    if created:
        db.add(WalletRegistration(device_id=device.id, pass_id=wallet_pass.id))
    await db.commit()
    return Response(status_code=201 if created else 200)


@router.delete("/v1/devices/{device_library_identifier}/registrations/{pass_type_identifier}/{serial_number}")
async def unregister_pass(device_library_identifier: str, pass_type_identifier: str, serial_number: str, authorization: str | None = Header(default=None), db: AsyncSession = Depends(get_db)):
    wallet_pass = await find_pass(db, pass_type_identifier, serial_number)
    check_apple_auth(authorization, wallet_pass)
    device = await db.scalar(select(WalletDevice).where(WalletDevice.device_library_identifier == device_library_identifier))
    if device:
        registration = await db.scalar(select(WalletRegistration).where(WalletRegistration.device_id == device.id, WalletRegistration.pass_id == wallet_pass.id))
        if registration:
            await db.delete(registration)
            await db.flush()
        count = await db.scalar(select(func.count()).select_from(WalletRegistration).where(WalletRegistration.device_id == device.id))
        if not count:
            await db.delete(device)
        await db.commit()
    return Response(status_code=200)


@router.get("/v1/devices/{device_library_identifier}/registrations/{pass_type_identifier}")
async def updated_passes(device_library_identifier: str, pass_type_identifier: str, passesUpdatedSince: int | None = None, db: AsyncSession = Depends(get_db)):
    query = (
        select(WalletPass)
        .join(WalletRegistration, WalletRegistration.pass_id == WalletPass.id)
        .join(WalletDevice, WalletDevice.id == WalletRegistration.device_id)
        .where(WalletDevice.device_library_identifier == device_library_identifier, WalletPass.pass_type_identifier == pass_type_identifier, WalletPass.status == "active")
    )
    if passesUpdatedSince is not None:
        query = query.where(WalletPass.update_tag > passesUpdatedSince)
    rows = list((await db.scalars(query)).all())
    if not rows:
        return Response(status_code=204)
    last_updated = max(x.update_tag for x in rows)
    return {"serialNumbers": [x.serial_number for x in rows], "lastUpdated": str(last_updated)}


@router.get("/v1/passes/{pass_type_identifier}/{serial_number}")
async def updated_pass(pass_type_identifier: str, serial_number: str, authorization: str | None = Header(default=None), db: AsyncSession = Depends(get_db)):
    wallet_pass = await find_pass(db, pass_type_identifier, serial_number)
    check_apple_auth(authorization, wallet_pass)
    credential, brand, customer, design = await pass_entities(db, wallet_pass)
    data = generate_pkpass_bytes(credential=credential, brand=brand, customer=customer, design=design, wallet_pass=wallet_pass)
    wallet_pass.last_generated_at = datetime.now(timezone.utc)
    await db.commit()
    return Response(data, media_type="application/vnd.apple.pkpass", headers={"Last-Modified": wallet_pass.updated_at.strftime("%a, %d %b %Y %H:%M:%S GMT"), "Cache-Control": "no-store"})


@router.post("/v1/log")
async def apple_logs(payload: dict):
    return Response(status_code=200)
