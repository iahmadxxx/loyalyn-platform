import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import PLATFORM_ROLES, brand_access, current_user
from app.core.security import hash_password
from app.db.session import get_db
from app.models import (
    AuditLog, Branch, Coupon, Employee, MembershipTier, Reward, User, UserBrandAccess,
)
from app.schemas.common import (
    BranchCreate, BranchUpdate, CouponCreate, CouponUpdate, RewardCreate, RewardUpdate,
    StaffCreate, StaffUpdate, TierCreate, TierUpdate,
)
from app.services.audit import add_audit

router = APIRouter()


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def branch_out(x: Branch) -> dict:
    return {
        "id": str(x.id), "brand_id": str(x.brand_id), "name": x.name,
        "address": x.address, "phone": x.phone, "manager_name": x.manager_name,
        "latitude": x.latitude, "longitude": x.longitude, "is_active": x.is_active,
        "created_at": x.created_at,
    }


def staff_out(x: Employee) -> dict:
    return {
        "id": str(x.id), "brand_id": str(x.brand_id), "branch_id": str(x.branch_id) if x.branch_id else None,
        "user_id": str(x.user_id) if x.user_id else None, "name": x.name, "email": x.email,
        "phone": x.phone, "role": x.role, "permissions": x.permissions or {}, "is_active": x.is_active,
        "created_at": x.created_at,
    }


@router.get("/branches")
async def list_branches(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, brand_id, permission="branches.view")
    rows = list((await db.scalars(select(Branch).where(Branch.brand_id == brand_id).order_by(Branch.created_at.desc()))).all())
    return [branch_out(x) for x in rows]


@router.post("/branches", status_code=201)
async def create_branch(payload: BranchCreate, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, payload.brand_id, permission="branches.manage")
    branch = Branch(**payload.model_dump())
    db.add(branch)
    await db.flush()
    add_audit(db, actor_id=user.id, action="branch_created", entity_type="branch", entity_id=branch.id, brand_id=payload.brand_id, details={"name": branch.name}, ip_address=request.client.host if request.client else None)
    await db.commit()
    await db.refresh(branch)
    return branch_out(branch)


@router.patch("/branches/{branch_id}")
async def update_branch(branch_id: uuid.UUID, payload: BranchUpdate, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    branch = await db.get(Branch, branch_id)
    if not branch:
        raise HTTPException(404, "الفرع غير موجود")
    await brand_access(db, user, branch.brand_id, permission="branches.manage")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(branch, field, value)
    add_audit(db, actor_id=user.id, action="branch_updated", entity_type="branch", entity_id=branch.id, brand_id=branch.brand_id, details=payload.model_dump(exclude_unset=True), ip_address=request.client.host if request.client else None)
    await db.commit()
    await db.refresh(branch)
    return branch_out(branch)


@router.get("/staff")
async def list_staff(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, brand_id, permission="staff.view")
    rows = list((await db.scalars(select(Employee).where(Employee.brand_id == brand_id).order_by(Employee.created_at.desc()))).all())
    return [staff_out(x) for x in rows]


@router.post("/staff", status_code=201)
async def create_staff(payload: StaffCreate, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    access = await brand_access(db, user, payload.brand_id, permission="staff.manage")
    if payload.role == "brand_admin" and user.role not in PLATFORM_ROLES and (not access or access.role != "brand_admin"):
        raise HTTPException(403, "لا يمكنك إنشاء مدير براند")
    account = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if account:
        if await db.scalar(select(UserBrandAccess).where(UserBrandAccess.user_id == account.id, UserBrandAccess.brand_id == payload.brand_id)):
            raise HTTPException(409, "هذا المستخدم مرتبط بالبراند مسبقًا")
        if account.role in PLATFORM_ROLES and user.role not in PLATFORM_ROLES:
            raise HTTPException(403, "لا يمكن لمدير البراند ربط حساب مدير المنصة")
        if user.role not in PLATFORM_ROLES:
            raise HTTPException(409, "البريد مرتبط بحساب موجود. اطلب من مدير المنصة ربطه بهذا البراند")
        # Platform owner may grant an existing account another brand, but the
        # account password and global platform role are never overwritten.
        account.full_name = payload.name or account.full_name
        account.is_active = True
    else:
        account = User(
            email=payload.email.lower(), full_name=payload.name,
            password_hash=hash_password(payload.password), role=payload.role,
            brand_id=payload.brand_id,
        )
        db.add(account)
        await db.flush()
    access_row = UserBrandAccess(
        user_id=account.id, brand_id=payload.brand_id, role=payload.role,
        branch_id=payload.branch_id, permissions=payload.permissions, is_active=True,
    )
    employee = Employee(
        brand_id=payload.brand_id, branch_id=payload.branch_id, user_id=account.id,
        name=payload.name, email=payload.email.lower(), phone=payload.phone,
        role=payload.role, permissions=payload.permissions, is_active=True,
    )
    db.add_all([access_row, employee])
    await db.flush()
    add_audit(db, actor_id=user.id, action="staff_created", entity_type="employee", entity_id=employee.id, brand_id=payload.brand_id, details={"email": employee.email, "role": employee.role}, ip_address=request.client.host if request.client else None)
    await db.commit()
    await db.refresh(employee)
    return staff_out(employee)


@router.patch("/staff/{employee_id}")
async def update_staff(employee_id: uuid.UUID, payload: StaffUpdate, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    employee = await db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(404, "الموظف غير موجود")
    await brand_access(db, user, employee.brand_id, permission="staff.manage")
    data = payload.model_dump(exclude_unset=True)
    password = data.pop("password", None)
    for field, value in data.items():
        setattr(employee, field, value)
    if employee.user_id:
        account = await db.get(User, employee.user_id)
        if account:
            account.full_name = employee.name
            # Per-brand roles live in UserBrandAccess. Never downgrade or elevate
            # a global account role while editing one brand membership.
            other_active_access = await db.scalar(
                select(UserBrandAccess).where(
                    UserBrandAccess.user_id == account.id,
                    UserBrandAccess.brand_id != employee.brand_id,
                    UserBrandAccess.is_active.is_(True),
                )
            )
            if password and other_active_access and user.role not in PLATFORM_ROLES:
                raise HTTPException(403, "تغيير كلمة مرور حساب مرتبط بأكثر من براند متاح لمدير المنصة فقط")
            if account.role not in PLATFORM_ROLES and not other_active_access:
                account.role = employee.role
            # A per-brand deactivation must not disable an account that still
            # manages another active brand. Platform accounts are always kept active.
            if employee.is_active:
                account.is_active = True
            elif account.role in PLATFORM_ROLES or other_active_access:
                account.is_active = True
            else:
                account.is_active = False
            if password:
                account.password_hash = hash_password(password)
        access_row = await db.scalar(select(UserBrandAccess).where(UserBrandAccess.user_id == employee.user_id, UserBrandAccess.brand_id == employee.brand_id))
        if access_row:
            access_row.role = employee.role
            access_row.branch_id = employee.branch_id
            access_row.permissions = employee.permissions
            access_row.is_active = employee.is_active
    add_audit(db, actor_id=user.id, action="staff_updated", entity_type="employee", entity_id=employee.id, brand_id=employee.brand_id, details=data, ip_address=request.client.host if request.client else None)
    await db.commit()
    await db.refresh(employee)
    return staff_out(employee)


@router.get("/tiers")
async def list_tiers(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, brand_id, permission="loyalty.view")
    rows = list((await db.scalars(select(MembershipTier).where(MembershipTier.brand_id == brand_id).order_by(MembershipTier.rank))).all())
    return [{"id": str(x.id), "name": x.name, "rank": x.rank, "color": x.color, "min_points": x.min_points, "min_spend": x.min_spend, "points_multiplier": x.points_multiplier, "benefits": x.benefits or {}, "is_active": x.is_active} for x in rows]


@router.post("/tiers", status_code=201)
async def create_tier(payload: TierCreate, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, payload.brand_id, permission="loyalty.manage")
    tier = MembershipTier(**payload.model_dump())
    db.add(tier)
    await db.commit()
    await db.refresh(tier)
    return {"id": str(tier.id)}


@router.delete("/tiers/{tier_id}")
async def delete_tier(tier_id: uuid.UUID, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    tier = await db.get(MembershipTier, tier_id)
    if not tier:
        raise HTTPException(404, "المستوى غير موجود")
    await brand_access(db, user, tier.brand_id, permission="loyalty.manage")
    tier.is_active = False
    await db.commit()
    return {"ok": True}


@router.get("/rewards")
async def list_rewards(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, brand_id, permission="loyalty.view")
    rows = list((await db.scalars(select(Reward).where(Reward.brand_id == brand_id).order_by(Reward.created_at.desc()))).all())
    return [{"id": str(x.id), "name": x.name, "description": x.description, "points_cost": x.points_cost, "stock": x.stock, "image_url": x.image_url, "is_active": x.is_active} for x in rows]


@router.post("/rewards", status_code=201)
async def create_reward(payload: RewardCreate, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, payload.brand_id, permission="loyalty.manage")
    reward = Reward(**payload.model_dump())
    db.add(reward)
    await db.commit()
    await db.refresh(reward)
    return {"id": str(reward.id)}


@router.patch("/rewards/{reward_id}/toggle")
async def toggle_reward(reward_id: uuid.UUID, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    reward = await db.get(Reward, reward_id)
    if not reward:
        raise HTTPException(404, "المكافأة غير موجودة")
    await brand_access(db, user, reward.brand_id, permission="loyalty.manage")
    reward.is_active = not reward.is_active
    await db.commit()
    return {"ok": True, "is_active": reward.is_active}


@router.get("/audit")
async def list_audit(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, brand_id, permission="audit.view")
    rows = list((await db.scalars(select(AuditLog).where(AuditLog.brand_id == brand_id).order_by(AuditLog.created_at.desc()).limit(300))).all())
    return [{"id": str(x.id), "action": x.action, "entity_type": x.entity_type, "entity_id": x.entity_id, "details": x.details or {}, "ip_address": x.ip_address, "created_at": x.created_at} for x in rows]


@router.patch("/tiers/{tier_id}")
async def update_tier(tier_id: uuid.UUID, payload: TierUpdate, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    tier = await db.get(MembershipTier, tier_id)
    if not tier:
        raise HTTPException(404, "المستوى غير موجود")
    await brand_access(db, user, tier.brand_id, permission="loyalty.manage")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tier, field, value)
    add_audit(db, actor_id=user.id, action="membership_tier_updated", entity_type="membership_tier", entity_id=tier.id, brand_id=tier.brand_id, details={"name": tier.name}, ip_address=request.client.host if request.client else None)
    await db.commit()
    await db.refresh(tier)
    return {"id": str(tier.id), "name": tier.name, "rank": tier.rank, "color": tier.color, "min_points": tier.min_points, "min_spend": tier.min_spend, "points_multiplier": tier.points_multiplier, "benefits": tier.benefits or {}, "is_active": tier.is_active}


@router.patch("/rewards/{reward_id}")
async def update_reward(reward_id: uuid.UUID, payload: RewardUpdate, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    reward = await db.get(Reward, reward_id)
    if not reward:
        raise HTTPException(404, "المكافأة غير موجودة")
    await brand_access(db, user, reward.brand_id, permission="loyalty.manage")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(reward, field, value)
    add_audit(db, actor_id=user.id, action="reward_updated", entity_type="reward", entity_id=reward.id, brand_id=reward.brand_id, details={"name": reward.name}, ip_address=request.client.host if request.client else None)
    await db.commit()
    await db.refresh(reward)
    return {"id": str(reward.id), "name": reward.name, "description": reward.description, "points_cost": reward.points_cost, "stock": reward.stock, "image_url": reward.image_url, "is_active": reward.is_active}


def coupon_out(coupon: Coupon) -> dict:
    return {
        "id": str(coupon.id), "brand_id": str(coupon.brand_id), "code": coupon.code,
        "name": coupon.name, "description": coupon.description, "reward_type": coupon.reward_type,
        "reward_value": float(coupon.reward_value or 0), "starts_at": coupon.starts_at,
        "ends_at": coupon.ends_at, "max_redemptions": coupon.max_redemptions,
        "per_customer_limit": coupon.per_customer_limit, "redemption_count": coupon.redemption_count,
        "is_active": coupon.is_active, "created_at": coupon.created_at,
    }


@router.get("/coupons")
async def list_coupons(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, brand_id, permission="loyalty.view")
    rows = list((await db.scalars(select(Coupon).where(Coupon.brand_id == brand_id).order_by(Coupon.created_at.desc()))).all())
    return [coupon_out(x) for x in rows]


@router.post("/coupons", status_code=201)
async def create_coupon(payload: CouponCreate, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, payload.brand_id, permission="loyalty.manage")
    if _aware(payload.ends_at) and _aware(payload.starts_at) and _aware(payload.ends_at) <= _aware(payload.starts_at):
        raise HTTPException(400, "تاريخ نهاية الكوبون يجب أن يكون بعد تاريخ البداية")
    if await db.scalar(select(Coupon).where(Coupon.brand_id == payload.brand_id, Coupon.code == payload.code)):
        raise HTTPException(409, "رمز الكوبون مستخدم داخل هذا البراند")
    coupon = Coupon(**payload.model_dump())
    db.add(coupon)
    await db.flush()
    add_audit(db, actor_id=user.id, action="coupon_created", entity_type="coupon", entity_id=coupon.id, brand_id=coupon.brand_id, details={"code": coupon.code, "name": coupon.name}, ip_address=request.client.host if request.client else None)
    await db.commit()
    await db.refresh(coupon)
    return coupon_out(coupon)


@router.patch("/coupons/{coupon_id}")
async def update_coupon(coupon_id: uuid.UUID, payload: CouponUpdate, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    coupon = await db.get(Coupon, coupon_id)
    if not coupon:
        raise HTTPException(404, "الكوبون غير موجود")
    await brand_access(db, user, coupon.brand_id, permission="loyalty.manage")
    data = payload.model_dump(exclude_unset=True)
    start = data.get("starts_at", coupon.starts_at)
    end = data.get("ends_at", coupon.ends_at)
    if _aware(start) and _aware(end) and _aware(end) <= _aware(start):
        raise HTTPException(400, "تاريخ نهاية الكوبون يجب أن يكون بعد تاريخ البداية")
    for field, value in data.items():
        setattr(coupon, field, value)
    add_audit(db, actor_id=user.id, action="coupon_updated", entity_type="coupon", entity_id=coupon.id, brand_id=coupon.brand_id, details=data, ip_address=request.client.host if request.client else None)
    await db.commit()
    await db.refresh(coupon)
    return coupon_out(coupon)
