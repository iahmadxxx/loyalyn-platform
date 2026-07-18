from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import PLATFORM_ROLES, current_user
from app.core.security import create_token, verify_password
from app.db.session import get_db
from app.models import Brand, User, UserBrandAccess
from app.schemas.common import Login

router = APIRouter()


@router.post("/login")
async def login(payload: Login, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "البريد الإلكتروني أو كلمة المرور غير صحيحة")
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    role = "platform_owner" if user.role in PLATFORM_ROLES else user.role
    return {
        "access_token": create_token(user.id, role),
        "token_type": "bearer",
        "user": {"id": str(user.id), "name": user.full_name, "email": user.email, "role": role},
    }


@router.get("/me")
async def me(user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    role = "platform_owner" if user.role in PLATFORM_ROLES else user.role
    if role == "platform_owner":
        brands = list((await db.scalars(select(Brand).order_by(Brand.name))).all())
        access = [{"id": str(b.id), "name": b.name, "slug": b.slug, "role": "platform_owner"} for b in brands]
    else:
        rows = (await db.execute(
            select(UserBrandAccess, Brand)
            .join(Brand, Brand.id == UserBrandAccess.brand_id)
            .where(UserBrandAccess.user_id == user.id, UserBrandAccess.is_active.is_(True), Brand.is_active.is_(True))
            .order_by(Brand.name)
        )).all()
        access = [{"id": str(b.id), "name": b.name, "slug": b.slug, "role": a.role, "permissions": a.permissions or {}} for a, b in rows]
        if not access and user.brand_id:
            brand = await db.get(Brand, user.brand_id)
            if brand:
                access = [{"id": str(brand.id), "name": brand.name, "slug": brand.slug, "role": role, "permissions": {}}]
    return {
        "id": str(user.id),
        "name": user.full_name,
        "email": user.email,
        "role": role,
        "brand_id": str(user.brand_id) if user.brand_id else None,
        "brands": access,
    }
