import secrets
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import PLATFORM_ROLES, brand_access, current_user, require_platform_owner
from app.core.security import hash_password
from app.db.session import get_db
from app.models import (
    AuditLog, Brand, BrandWalletDesign, Employee, LoyaltyProgram, MembershipTier, StampProgram,
    User, UserBrandAccess,
)
from app.schemas.common import BrandCreate, BrandProgramProfileUpdate, BrandUpdate
from app.services.audit import add_audit
from app.services.capabilities import brand_capabilities, loyalty_program_type, normalized_mode

router = APIRouter()


def serialize_brand(brand: Brand) -> dict:
    return {
        "id": str(brand.id),
        "name": brand.name,
        "slug": brand.slug,
        "logo_url": brand.logo_url,
        "primary_color": brand.primary_color,
        "accent_color": brand.accent_color,
        "currency": brand.currency,
        "timezone": brand.timezone,
        "locale": brand.locale,
        "program_mode": normalized_mode(brand.program_mode),
        "feature_flags": brand.feature_flags or {},
        "capabilities": brand_capabilities(brand),
        "join_enabled": brand.join_enabled,
        "join_require_email": brand.join_require_email,
        "join_welcome_text": brand.join_welcome_text,
        "join_url": f"/join/{brand.slug}",
        "is_active": brand.is_active,
        "created_at": brand.created_at,
    }


@router.get("")
async def list_brands(db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    if user.role in PLATFORM_ROLES:
        rows = list((await db.scalars(select(Brand).order_by(Brand.created_at.desc()))).all())
    else:
        query = (
            select(Brand)
            .join(UserBrandAccess, UserBrandAccess.brand_id == Brand.id)
            .where(UserBrandAccess.user_id == user.id, UserBrandAccess.is_active.is_(True))
            .order_by(Brand.name)
        )
        rows = list((await db.scalars(query)).all())
        if not rows and user.brand_id:
            brand = await db.get(Brand, user.brand_id)
            rows = [brand] if brand else []
    return [serialize_brand(x) for x in rows]


@router.post("", status_code=201)
async def create_brand(
    payload: BrandCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_platform_owner),
):
    if await db.scalar(select(Brand).where(Brand.slug == payload.slug)):
        raise HTTPException(409, "رابط البراند مستخدم مسبقًا")
    brand = Brand(
        name=payload.name,
        slug=payload.slug,
        primary_color=payload.primary_color,
        accent_color=payload.accent_color,
        currency=payload.currency,
        timezone=payload.timezone,
        locale=payload.locale,
        program_mode=payload.program_mode,
        feature_flags=payload.feature_flags,
        join_enabled=payload.join_enabled,
        join_require_email=payload.join_require_email,
        join_welcome_text=payload.join_welcome_text,
    )
    db.add(brand)
    await db.flush()
    capabilities = brand_capabilities(brand)
    db.add(LoyaltyProgram(brand_id=brand.id, program_type=loyalty_program_type(brand.program_mode, capabilities)))
    db.add(BrandWalletDesign(
        brand_id=brand.id,
        background_color=payload.primary_color,
        label_color=payload.accent_color,
        logo_text=payload.name,
        card_title="بطاقة الولاء",
        fields={
            "show_points": capabilities.get("points", False),
            "show_stamps": capabilities.get("stamps", False),
            "show_rewards": capabilities.get("rewards", False),
            "show_tier": capabilities.get("tiers", False),
            "show_visits": True,
        },
    ))
    if capabilities.get("stamps"):
        db.add(StampProgram(
            brand_id=brand.id, name="البطاقة الرئيسية", slug="main-card",
            description="بطاقة الأختام الافتراضية", required_stamps=10,
            reward_title="مكافأة مجانية", stamp_icon="coffee",
            background_color=payload.primary_color, accent_color=payload.accent_color,
            is_default=True, sort_order=0,
        ))
    db.add_all([
        MembershipTier(brand_id=brand.id, name="برونزي", rank=0, color="#B7791F", min_points=0),
        MembershipTier(brand_id=brand.id, name="فضي", rank=1, color="#A0AEC0", min_points=500),
        MembershipTier(brand_id=brand.id, name="ذهبي", rank=2, color="#D69E2E", min_points=1500),
        MembershipTier(brand_id=brand.id, name="VIP", rank=3, color="#C6FF4A", min_points=5000),
    ])
    manager_info = None
    if payload.manager_email:
        manager = await db.scalar(select(User).where(User.email == payload.manager_email.lower()))
        generated_password: str | None = None
        if manager:
            if not manager.is_active:
                manager.is_active = True
            manager.full_name = payload.manager_name or manager.full_name
            # An existing account keeps its password. Brand creation only grants
            # access; password resets are a separate, explicit administration action.
        else:
            generated_password = payload.manager_password or secrets.token_urlsafe(12)
            manager = User(
                email=payload.manager_email.lower(),
                full_name=payload.manager_name or payload.manager_email.split("@")[0],
                password_hash=hash_password(generated_password),
                role="brand_admin",
                brand_id=brand.id,
            )
            db.add(manager)
            await db.flush()
        existing = await db.scalar(select(UserBrandAccess).where(UserBrandAccess.user_id == manager.id, UserBrandAccess.brand_id == brand.id))
        if not existing:
            db.add(UserBrandAccess(user_id=manager.id, brand_id=brand.id, role="brand_admin", permissions={}, is_active=True))
        employee = await db.scalar(select(Employee).where(Employee.brand_id == brand.id, Employee.email == manager.email))
        if not employee:
            db.add(Employee(
                brand_id=brand.id,
                user_id=manager.id,
                name=manager.full_name,
                email=manager.email,
                role="brand_admin",
                permissions={},
            ))
        manager_info = {"email": manager.email, "temporary_password": generated_password if not payload.manager_password else None, "existing_account": generated_password is None}
    add_audit(
        db,
        actor_id=user.id,
        action="brand_created",
        entity_type="brand",
        entity_id=brand.id,
        brand_id=brand.id,
        details={"name": brand.name, "manager_email": str(payload.manager_email) if payload.manager_email else None},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(brand)
    return {"brand": serialize_brand(brand), "manager": manager_info}


@router.patch("/{brand_id}/program-profile")
async def update_program_profile(
    brand_id: uuid.UUID,
    payload: BrandProgramProfileUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(current_user),
):
    await brand_access(db, user, brand_id, permission="brand.manage")
    brand = await db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(404, "البراند غير موجود")
    brand.program_mode = payload.program_mode
    brand.feature_flags = payload.feature_flags
    brand.join_enabled = payload.join_enabled
    brand.join_require_email = payload.join_require_email
    brand.join_welcome_text = payload.join_welcome_text
    capabilities = brand_capabilities(brand)
    program = await db.scalar(select(LoyaltyProgram).where(LoyaltyProgram.brand_id == brand_id))
    if not program:
        program = LoyaltyProgram(brand_id=brand_id)
        db.add(program)
    program.program_type = loyalty_program_type(brand.program_mode, capabilities)
    design = await db.scalar(select(BrandWalletDesign).where(BrandWalletDesign.brand_id == brand_id))
    if design:
        fields = dict(design.fields or {})
        fields.update({
            "show_points": capabilities.get("points", False),
            "show_stamps": capabilities.get("stamps", False),
            "show_rewards": capabilities.get("rewards", False),
            "show_tier": capabilities.get("tiers", False),
        })
        design.fields = fields
        design.draft_version += 1
    if capabilities.get("stamps"):
        existing = await db.scalar(select(StampProgram).where(StampProgram.brand_id == brand_id))
        if not existing:
            db.add(StampProgram(
                brand_id=brand_id, name="البطاقة الرئيسية", slug="main-card",
                description="بطاقة الأختام الافتراضية", required_stamps=10,
                reward_title="مكافأة مجانية", background_color=brand.primary_color,
                accent_color=brand.accent_color, is_default=True,
            ))
    add_audit(
        db, actor_id=user.id, action="brand_program_profile_updated", entity_type="brand",
        entity_id=brand.id, brand_id=brand.id,
        details={"program_mode": brand.program_mode, "feature_flags": brand.feature_flags},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(brand)
    return serialize_brand(brand)


@router.get("/{brand_id}")
async def get_brand(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, brand_id, permission="brand.view")
    brand = await db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(404, "البراند غير موجود")
    return serialize_brand(brand)


@router.patch("/{brand_id}")
async def update_brand(
    brand_id: uuid.UUID,
    payload: BrandUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(current_user),
):
    await brand_access(db, user, brand_id, permission="brand.manage")
    brand = await db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(404, "البراند غير موجود")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(brand, field, value)
    add_audit(
        db,
        actor_id=user.id,
        action="brand_updated",
        entity_type="brand",
        entity_id=brand.id,
        brand_id=brand.id,
        details=payload.model_dump(exclude_unset=True),
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(brand)
    return serialize_brand(brand)
