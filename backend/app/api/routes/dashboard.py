import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import PLATFORM_ROLES, brand_access, current_user
from app.db.session import get_db
from app.models import Brand, Branch, Customer, Employee, LoyaltyTransaction, NotificationCampaign, WalletPass

router = APIRouter()


@router.get("")
async def dashboard(brand_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    if brand_id:
        await brand_access(db, user, brand_id, permission="brand.view")
    elif user.role not in PLATFORM_ROLES:
        brand_id = user.brand_id
    filters = [Customer.brand_id == brand_id] if brand_id else []
    tx_filters = [LoyaltyTransaction.brand_id == brand_id] if brand_id else []
    branch_filters = [Branch.brand_id == brand_id] if brand_id else []
    employee_filters = [Employee.brand_id == brand_id] if brand_id else []
    campaign_filters = [NotificationCampaign.brand_id == brand_id] if brand_id else []
    pass_filters = [WalletPass.brand_id == brand_id] if brand_id else []
    start = datetime.now(timezone.utc) - timedelta(days=30)
    customers = await db.scalar(select(func.count()).select_from(Customer).where(*filters, Customer.is_active.is_(True)))
    new_customers = await db.scalar(select(func.count()).select_from(Customer).where(*filters, Customer.created_at >= start))
    branches = await db.scalar(select(func.count()).select_from(Branch).where(*branch_filters, Branch.is_active.is_(True)))
    staff = await db.scalar(select(func.count()).select_from(Employee).where(*employee_filters, Employee.is_active.is_(True)))
    transactions = await db.scalar(select(func.count()).select_from(LoyaltyTransaction).where(*tx_filters))
    points_issued = await db.scalar(select(func.coalesce(func.sum(LoyaltyTransaction.delta_points), 0)).where(*tx_filters, LoyaltyTransaction.delta_points > 0))
    campaigns = await db.scalar(select(func.count()).select_from(NotificationCampaign).where(*campaign_filters))
    passes = await db.scalar(select(func.count()).select_from(WalletPass).where(*pass_filters, WalletPass.status == "active"))
    brands = await db.scalar(select(func.count()).select_from(Brand)) if user.role in PLATFORM_ROLES else 1
    recent = list((await db.scalars(select(LoyaltyTransaction).where(*tx_filters).order_by(LoyaltyTransaction.created_at.desc()).limit(12))).all())
    return {
        "brands": brands or 0, "customers": customers or 0, "new_customers_30d": new_customers or 0,
        "branches": branches or 0, "staff": staff or 0, "transactions": transactions or 0,
        "points_issued": int(points_issued or 0), "campaigns": campaigns or 0, "wallet_passes": passes or 0,
        "recent_activity": [{"id": str(x.id), "action": x.action, "delta_points": x.delta_points, "delta_stamps": x.delta_stamps, "created_at": x.created_at} for x in recent],
    }
