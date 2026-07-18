import secrets
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import PLATFORM_ROLES, brand_access, current_user, require_platform_owner
from app.core.security import hash_password
from app.db.session import get_db
from app.models import (
    AuditLog, Brand, BrandWalletDesign, Employee, LoyaltyProgram, MembershipTier,
    User, UserBrandAccess,
)
from app.schemas.common import BrandCreate, BrandUpdate
from app.services.audit import add_audit

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
    )
    db.add(brand)
    await db.flush()
    db.add(LoyaltyProgram(brand_id=brand.id))
    db.add(BrandWalletDesign(
        brand_id=brand.id,
        background_color=payload.primary_color,
        label_color=payload.accent_color,
        logo_text=payload.name,
        card_title="بطاقة الولاء",
        fields={"show_points": True, "show_stamps": True, "show_rewards": True, "show_tier": True, "show_visits": True},
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
