from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models import Brand, LoyaltyProgram, WalletConfig, WalletDesign
from app.schemas.common import BrandCreate

router = APIRouter()

@router.get("")
async def list_brands(db: AsyncSession = Depends(get_db)):
    result = await db.scalars(select(Brand).order_by(Brand.created_at.desc()))
    return [{"id": str(b.id), "name": b.name, "slug": b.slug, "is_active": b.is_active, "primary_color": b.primary_color, "accent_color": b.accent_color} for b in result]

@router.post("", status_code=201)
async def create_brand(payload: BrandCreate, db: AsyncSession = Depends(get_db)):
    if await db.scalar(select(Brand).where(Brand.slug == payload.slug)):
        raise HTTPException(409, "Brand slug already exists")
    brand = Brand(**payload.model_dump())
    db.add(brand)
    await db.flush()
    db.add_all([
        LoyaltyProgram(brand_id=brand.id, required_stamps=6, reward_title="Your reward is ready"),
        WalletConfig(brand_id=brand.id),
        WalletDesign(brand_id=brand.id, version=1, is_published=True, design={"template": "signature", "showProgress": True}),
    ])
    await db.commit()
    await db.refresh(brand)
    return {"id": str(brand.id), "name": brand.name, "slug": brand.slug}
