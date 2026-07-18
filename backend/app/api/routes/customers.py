import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models import Customer
from app.schemas.common import CustomerCreate, StampAction
from app.services.loyalty import add_stamp

router = APIRouter()

@router.post("", status_code=201)
async def create_customer(payload: CustomerCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(Customer).where(Customer.brand_id == payload.brand_id, Customer.phone == payload.phone))
    if existing:
        return {"id": str(existing.id), "membership_code": existing.membership_code, "existing": True}
    customer = Customer(brand_id=payload.brand_id, name=payload.name, phone=payload.phone, membership_code=secrets.token_urlsafe(18))
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return {"id": str(customer.id), "membership_code": customer.membership_code, "existing": False}

@router.get("/{membership_code}")
async def get_customer(membership_code: str, db: AsyncSession = Depends(get_db)):
    customer = await db.scalar(select(Customer).where(Customer.membership_code == membership_code))
    if not customer:
        raise HTTPException(404, "Customer not found")
    return {"id": str(customer.id), "name": customer.name, "stamps": customer.stamps, "available_rewards": customer.available_rewards, "membership_code": customer.membership_code}

@router.post("/{membership_code}/stamps")
async def stamp_customer(membership_code: str, payload: StampAction, db: AsyncSession = Depends(get_db)):
    customer = await db.scalar(select(Customer).where(Customer.membership_code == membership_code).with_for_update())
    if not customer:
        raise HTTPException(404, "Customer not found")
    customer, tx, applied = await add_stamp(db, customer, payload.branch_id, None, payload.idempotency_key)
    return {"applied": applied, "stamps": customer.stamps, "available_rewards": customer.available_rewards, "transaction_id": str(tx.id)}
