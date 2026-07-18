import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import PLATFORM_ROLES, brand_access, current_user, effective_permissions, operational_branch
from app.db.session import get_db
from app.models import Brand, Branch, CardTemplate, Coupon, CouponRedemption, Customer, CustomerStampCard, LoyaltyProgram, LoyaltyTransaction, Reward, StampProgram, WalletPass
from app.schemas.common import (
    CouponRedeem, CustomerCreate, CustomerUpdate, EarnedRewardRedeem, LoyaltyApply,
    LoyaltyProgramUpdate, RewardRedeem, TransactionReverse,
)
from app.services.audit import add_audit
from app.services.capabilities import brand_capabilities, loyalty_program_type
from app.services.cards import attach_template
from app.services.loyalty import apply_loyalty, consume_point_buckets, program_dict, recalculate_tier
from app.services.wallet import push_pass_update

router = APIRouter()


async def ensure_branch(db: AsyncSession, branch_id: uuid.UUID | None, brand_id: uuid.UUID) -> None:
    if not branch_id:
        return
    branch = await db.get(Branch, branch_id)
    if not branch or branch.brand_id != brand_id or not branch.is_active:
        raise HTTPException(400, "الفرع غير موجود داخل هذا البراند أو أنه موقوف")


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def customer_out(customer: Customer, *, limited: bool = False) -> dict:
    data = {
        "id": str(customer.id), "brand_id": str(customer.brand_id),
        "home_branch_id": str(customer.home_branch_id) if customer.home_branch_id else None, "name": customer.name,
        "phone": customer.phone, "email": customer.email, "birthday": customer.birthday,
        "membership_code": customer.membership_code, "points": customer.points,
        "stamps": customer.stamps, "available_rewards": customer.available_rewards,
        "tier": customer.tier, "visits": customer.visits, "total_spend": float(customer.total_spend or 0),
        "last_visit_at": customer.last_visit_at, "tags": customer.tags or [], "notes": customer.notes,
        "is_active": customer.is_active, "created_at": customer.created_at,
    }
    if limited:
        for key in ("email", "birthday", "tags", "notes", "total_spend"):
            data.pop(key, None)
    return data


def transaction_out(tx: LoyaltyTransaction) -> dict:
    return {
        "id": str(tx.id), "action": tx.action, "delta_points": tx.delta_points,
        "delta_stamps": tx.delta_stamps, "points_before": tx.points_before,
        "points_after": tx.points_after, "stamps_before": tx.stamps_before,
        "stamps_after": tx.stamps_after, "amount": float(tx.amount or 0),
        "reference": tx.reference, "expires_at": tx.expires_at,
        "remaining_points": tx.remaining_points, "metadata": tx.metadata_json or {}, "created_at": tx.created_at,
    }


@router.get("")
async def list_customers(
    brand_id: uuid.UUID,
    q: str | None = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    user=Depends(current_user),
):
    access = await brand_access(db, user, brand_id, permission="customers.view")
    role = "platform_owner" if user.role in PLATFORM_ROLES else (access.role if access else user.role)
    permissions = {"*": True} if role == "platform_owner" else effective_permissions(role, access.permissions if access else {})
    limited = not permissions.get("*", False) and not permissions.get("customers.list", False)
    if limited and (not q or len(q.strip()) < 2):
        return []
    query = select(Customer).where(Customer.brand_id == brand_id)
    if active_only:
        query = query.where(Customer.is_active.is_(True))
    if q:
        term = f"%{q.strip()}%"
        fields = [Customer.name.ilike(term), Customer.phone.ilike(term), Customer.membership_code.ilike(term)]
        if not limited:
            fields.append(Customer.email.ilike(term))
        query = query.where(or_(*fields))
    rows = list((await db.scalars(query.order_by(Customer.created_at.desc()).limit(25 if limited else 1000))).all())
    return [customer_out(x, limited=limited) for x in rows]


@router.post("", status_code=201)
async def create_customer(payload: CustomerCreate, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    access = await brand_access(db, user, payload.brand_id, permission="customers.create")
    data = payload.model_dump()
    requested_template_id = data.pop("card_template_id", None)
    data["home_branch_id"] = operational_branch(access, payload.home_branch_id)
    await ensure_branch(db, data["home_branch_id"], payload.brand_id)
    existing = await db.scalar(select(Customer).where(Customer.brand_id == payload.brand_id, Customer.phone == payload.phone))
    if existing:
        raise HTTPException(409, "يوجد عميل بنفس رقم الهاتف داخل هذا البراند")
    customer = Customer(**data, membership_code=secrets.token_urlsafe(18))
    db.add(customer)
    await db.flush()
    brand = await db.get(Brand, payload.brand_id)
    if brand and brand_capabilities(brand).get("stamps") and requested_template_id:
        template = await db.get(CardTemplate, requested_template_id)
        if not template or template.brand_id != brand.id or template.status != "published":
            raise HTTPException(422, "البطاقة المختارة غير متاحة أو لم تُنشر بعد")
        await attach_template(db, customer, template, actor_id=user.id)
    add_audit(db, actor_id=user.id, action="customer_created", entity_type="customer", entity_id=customer.id, brand_id=payload.brand_id, details={"name": customer.name, "phone": customer.phone}, ip_address=request.client.host if request.client else None)
    await db.commit()
    await db.refresh(customer)
    return customer_out(customer)


@router.get("/{customer_id}")
async def get_customer(customer_id: uuid.UUID, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(404, "العميل غير موجود")
    access = await brand_access(db, user, customer.brand_id, permission="customers.view")
    role = "platform_owner" if user.role in PLATFORM_ROLES else (access.role if access else user.role)
    permissions = {"*": True} if role == "platform_owner" else effective_permissions(role, access.permissions if access else {})
    limited = not any(permissions.get(key, False) for key in ("*", "customers.list", "customers.edit", "customers.history"))
    return customer_out(customer, limited=limited)


@router.patch("/{customer_id}")
async def update_customer(customer_id: uuid.UUID, payload: CustomerUpdate, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(404, "العميل غير موجود")
    access = await brand_access(db, user, customer.brand_id, permission="customers.edit")
    data = payload.model_dump(exclude_unset=True)
    if "home_branch_id" in data:
        data["home_branch_id"] = operational_branch(access, data["home_branch_id"])
        await ensure_branch(db, data["home_branch_id"], customer.brand_id)
    if "phone" in data:
        duplicate = await db.scalar(select(Customer).where(Customer.brand_id == customer.brand_id, Customer.phone == data["phone"], Customer.id != customer.id))
        if duplicate:
            raise HTTPException(409, "رقم الهاتف مرتبط بعميل آخر")
    for field, value in data.items():
        setattr(customer, field, value)
    add_audit(db, actor_id=user.id, action="customer_updated", entity_type="customer", entity_id=customer.id, brand_id=customer.brand_id, details=data, ip_address=request.client.host if request.client else None)
    await db.commit()
    await db.refresh(customer)
    return customer_out(customer)


@router.get("/{customer_id}/ledger")
async def customer_ledger(customer_id: uuid.UUID, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(404, "العميل غير موجود")
    await brand_access(db, user, customer.brand_id, permission="customers.history")
    rows = list((await db.scalars(select(LoyaltyTransaction).where(LoyaltyTransaction.customer_id == customer_id).order_by(LoyaltyTransaction.created_at.desc()).limit(500))).all())
    return [transaction_out(x) for x in rows]


@router.get("/program/{brand_id}")
async def get_program(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, brand_id, permission="loyalty.manage")
    program = await db.scalar(select(LoyaltyProgram).where(LoyaltyProgram.brand_id == brand_id))
    if not program:
        program = LoyaltyProgram(brand_id=brand_id)
        db.add(program)
        await db.commit()
        await db.refresh(program)
    return program_dict(program)


@router.put("/program/{brand_id}")
async def update_program(brand_id: uuid.UUID, payload: LoyaltyProgramUpdate, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, brand_id, permission="loyalty.manage")
    brand = await db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(404, "البراند غير موجود")
    capabilities = brand_capabilities(brand)
    expected_type = loyalty_program_type(brand.program_mode, capabilities)
    if brand.program_mode != "custom" and payload.program_type != expected_type:
        raise HTTPException(409, "نوع برنامج الولاء مرتبط بإعدادات البراند. غيّره من إعدادات نوع البرنامج.")
    if payload.cashback_percent and not capabilities.get("cashback"):
        raise HTTPException(409, "ميزة Cashback غير مفعلة لهذا البراند")
    program = await db.scalar(select(LoyaltyProgram).where(LoyaltyProgram.brand_id == brand_id))
    if not program:
        program = LoyaltyProgram(brand_id=brand_id)
        db.add(program)
    for field, value in payload.model_dump().items():
        setattr(program, field, value)
    add_audit(db, actor_id=user.id, action="loyalty_program_updated", entity_type="loyalty_program", entity_id=program.id, brand_id=brand_id, details=payload.model_dump(), ip_address=request.client.host if request.client else None)
    await db.commit()
    await db.refresh(program)
    return program_dict(program)


@router.post("/{customer_id}/loyalty")
async def apply_customer_loyalty(customer_id: uuid.UUID, payload: LoyaltyApply, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    customer = await db.scalar(select(Customer).where(Customer.id == customer_id).with_for_update())
    if not customer:
        raise HTTPException(404, "العميل غير موجود")
    permission = "loyalty.manual" if payload.action == "manual" else "loyalty.apply"
    access = await brand_access(db, user, customer.brand_id, permission=permission)
    branch_id = operational_branch(access, payload.branch_id)
    brand = await db.get(Brand, customer.brand_id)
    capabilities = brand_capabilities(brand) if brand else {}
    if capabilities.get("multi_stamp_cards") and payload.action in {"visit", "spend"} and not capabilities.get("points"):
        raise HTTPException(409, "استخدم السكان السريع واختر بطاقة الأختام المطلوبة")
    if capabilities.get("multi_stamp_cards") and payload.stamps:
        raise HTTPException(409, "الأختام تُضاف إلى بطاقة محددة من السكان السريع")
    if payload.points and not capabilities.get("points"):
        raise HTTPException(409, "ميزة النقاط غير مفعلة لهذا البراند")
    if payload.stamps and not capabilities.get("stamps"):
        raise HTTPException(409, "ميزة الأختام غير مفعلة لهذا البراند")
    await ensure_branch(db, branch_id, customer.brand_id)
    program = await db.scalar(select(LoyaltyProgram).where(LoyaltyProgram.brand_id == customer.brand_id))
    if not program:
        program = LoyaltyProgram(brand_id=customer.brand_id)
        db.add(program)
        await db.flush()
    try:
        transaction, duplicate = await apply_loyalty(
            db, customer, program, actor_id=user.id, action=payload.action,
            branch_id=branch_id, amount=payload.amount, points=payload.points,
            stamps=payload.stamps, note=payload.note, reference=payload.reference,
            idempotency_key=payload.idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not duplicate:
        add_audit(db, actor_id=user.id, action="loyalty_applied", entity_type="customer", entity_id=customer.id, brand_id=customer.brand_id, details={"action": payload.action, "delta_points": transaction.delta_points, "delta_stamps": transaction.delta_stamps}, ip_address=request.client.host if request.client else None)
        wallet_pass = await db.scalar(select(WalletPass).where(WalletPass.customer_id == customer.id, WalletPass.status == "active"))
        if wallet_pass:
            wallet_pass.update_tag += 1
        await db.commit()
        if wallet_pass:
            await push_pass_update(db, wallet_pass)
            await db.commit()
    await db.refresh(customer)
    return {"customer": customer_out(customer), "transaction": transaction_out(transaction), "duplicate": duplicate}


@router.post("/{customer_id}/redeem")
async def redeem_reward(customer_id: uuid.UUID, payload: RewardRedeem, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    customer = await db.scalar(select(Customer).where(Customer.id == customer_id).with_for_update())
    reward = await db.scalar(select(Reward).where(Reward.id == payload.reward_id).with_for_update())
    if not customer or not reward or customer.brand_id != reward.brand_id or not reward.is_active:
        raise HTTPException(404, "العميل أو المكافأة غير موجود")
    access = await brand_access(db, user, customer.brand_id, permission="rewards.redeem")
    branch_id = operational_branch(access, payload.branch_id)
    brand = await db.get(Brand, customer.brand_id)
    capabilities = brand_capabilities(brand) if brand else {}
    if not capabilities.get("points") or not capabilities.get("rewards"):
        raise HTTPException(409, "مكافآت النقاط غير مفعلة لهذا البراند")
    await ensure_branch(db, branch_id, customer.brand_id)
    old = await db.scalar(select(LoyaltyTransaction).where(LoyaltyTransaction.idempotency_key == payload.idempotency_key))
    if old:
        return {"customer": customer_out(customer), "duplicate": True}
    if customer.points < reward.points_cost:
        raise HTTPException(400, "رصيد النقاط غير كافٍ")
    if reward.stock is not None and reward.stock <= 0:
        raise HTTPException(400, "المكافأة نفدت")
    before = customer.points
    customer.points -= reward.points_cost
    await consume_point_buckets(db, customer.id, reward.points_cost)
    await recalculate_tier(db, customer)
    if reward.stock is not None:
        reward.stock -= 1
    tx = LoyaltyTransaction(
        brand_id=customer.brand_id, branch_id=branch_id, customer_id=customer.id,
        actor_id=user.id, action="redeem_reward", delta_points=-reward.points_cost,
        points_before=before, points_after=customer.points, stamps_before=customer.stamps,
        stamps_after=customer.stamps, amount=Decimal("0"), idempotency_key=payload.idempotency_key,
        metadata_json={"reward_id": str(reward.id), "reward_name": reward.name},
    )
    db.add(tx)
    add_audit(db, actor_id=user.id, action="reward_redeemed", entity_type="reward", entity_id=reward.id, brand_id=customer.brand_id, details={"customer_id": str(customer.id), "points": reward.points_cost}, ip_address=request.client.host if request.client else None)
    wallet_pass = await db.scalar(select(WalletPass).where(WalletPass.customer_id == customer.id, WalletPass.status == "active"))
    if wallet_pass:
        wallet_pass.update_tag += 1
    await db.commit()
    if wallet_pass:
        await push_pass_update(db, wallet_pass)
        await db.commit()
    await db.refresh(customer)
    return {"customer": customer_out(customer), "duplicate": False}


@router.post("/{customer_id}/redeem-earned")
async def redeem_earned_reward(
    customer_id: uuid.UUID,
    payload: EarnedRewardRedeem,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(current_user),
):
    customer = await db.scalar(select(Customer).where(Customer.id == customer_id).with_for_update())
    if not customer:
        raise HTTPException(404, "العميل غير موجود")
    access = await brand_access(db, user, customer.brand_id, permission="rewards.redeem")
    branch_id = operational_branch(access, payload.branch_id)
    brand = await db.get(Brand, customer.brand_id)
    capabilities = brand_capabilities(brand) if brand else {}
    if capabilities.get("multi_stamp_cards"):
        raise HTTPException(409, "اختر بطاقة الأختام وصرف مكافأتها من السكان السريع")
    if not capabilities.get("rewards"):
        raise HTTPException(409, "ميزة المكافآت غير مفعلة لهذا البراند")
    await ensure_branch(db, branch_id, customer.brand_id)
    old = await db.scalar(
        select(LoyaltyTransaction).where(LoyaltyTransaction.idempotency_key == payload.idempotency_key)
    )
    if old:
        return {"customer": customer_out(customer), "transaction": transaction_out(old), "duplicate": True}
    if customer.available_rewards <= 0:
        raise HTTPException(400, "لا توجد مكافأة أختام أو نقاط جاهزة للاستبدال")
    program = await db.scalar(select(LoyaltyProgram).where(LoyaltyProgram.brand_id == customer.brand_id))
    customer.available_rewards -= 1
    tx = LoyaltyTransaction(
        brand_id=customer.brand_id,
        branch_id=branch_id,
        customer_id=customer.id,
        actor_id=user.id,
        action="redeem_earned",
        delta_points=0,
        delta_stamps=0,
        points_before=customer.points,
        points_after=customer.points,
        stamps_before=customer.stamps,
        stamps_after=customer.stamps,
        amount=Decimal("0"),
        idempotency_key=payload.idempotency_key,
        metadata_json={"reward_title": program.stamp_reward_title if program else "مكافأة مجانية"},
    )
    db.add(tx)
    add_audit(
        db,
        actor_id=user.id,
        action="earned_reward_redeemed",
        entity_type="customer",
        entity_id=customer.id,
        brand_id=customer.brand_id,
        details={"remaining_rewards": customer.available_rewards},
        ip_address=request.client.host if request.client else None,
    )
    wallet_pass = await db.scalar(
        select(WalletPass).where(WalletPass.customer_id == customer.id, WalletPass.status == "active")
    )
    if wallet_pass:
        wallet_pass.update_tag += 1
    await db.commit()
    await db.refresh(tx)
    await db.refresh(customer)
    if wallet_pass:
        await push_pass_update(db, wallet_pass)
        await db.commit()
    return {"customer": customer_out(customer), "transaction": transaction_out(tx), "duplicate": False}


@router.post("/{customer_id}/coupons/redeem")
async def redeem_coupon(
    customer_id: uuid.UUID,
    payload: CouponRedeem,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(current_user),
):
    customer = await db.scalar(select(Customer).where(Customer.id == customer_id).with_for_update())
    if not customer:
        raise HTTPException(404, "العميل غير موجود")
    access = await brand_access(db, user, customer.brand_id, permission="rewards.redeem")
    branch_id = operational_branch(access, payload.branch_id)
    brand = await db.get(Brand, customer.brand_id)
    if not brand or not brand_capabilities(brand).get("coupons"):
        raise HTTPException(409, "ميزة الكوبونات غير مفعلة لهذا البراند")
    await ensure_branch(db, branch_id, customer.brand_id)
    duplicate = await db.scalar(
        select(CouponRedemption).where(CouponRedemption.idempotency_key == payload.idempotency_key)
    )
    if duplicate:
        return {"customer": customer_out(customer), "benefit": duplicate.benefit or {}, "duplicate": True}
    coupon = await db.scalar(
        select(Coupon).where(
            Coupon.brand_id == customer.brand_id,
            Coupon.code == payload.code.strip().upper(),
            Coupon.is_active.is_(True),
        ).with_for_update()
    )
    if not coupon:
        raise HTTPException(404, "الكوبون غير موجود أو موقوف")
    now = datetime.now(timezone.utc)
    if _aware(coupon.starts_at) and _aware(coupon.starts_at) > now:
        raise HTTPException(400, "الكوبون لم يبدأ بعد")
    if _aware(coupon.ends_at) and _aware(coupon.ends_at) < now:
        raise HTTPException(400, "انتهت صلاحية الكوبون")
    if coupon.max_redemptions is not None and coupon.redemption_count >= coupon.max_redemptions:
        raise HTTPException(400, "وصل الكوبون إلى الحد الأقصى للاستخدام")
    customer_uses = await db.scalar(
        select(func.count())
        .select_from(CouponRedemption)
        .where(CouponRedemption.coupon_id == coupon.id, CouponRedemption.customer_id == customer.id)
    )
    if int(customer_uses or 0) >= coupon.per_customer_limit:
        raise HTTPException(400, "استخدم العميل هذا الكوبون بالحد المسموح")

    benefit = {"type": coupon.reward_type, "value": float(coupon.reward_value), "name": coupon.name}
    program = await db.scalar(select(LoyaltyProgram).where(LoyaltyProgram.brand_id == customer.brand_id))
    if not program:
        program = LoyaltyProgram(brand_id=customer.brand_id)
        db.add(program)
        await db.flush()
    points = int(coupon.reward_value) if coupon.reward_type == "points" else 0
    stamps = int(coupon.reward_value) if coupon.reward_type == "stamps" else 0
    tx, _ = await apply_loyalty(
        db,
        customer,
        program,
        actor_id=user.id,
        action="coupon",
        branch_id=branch_id,
        amount=Decimal("0"),
        points=points,
        stamps=stamps,
        note=f"كوبون {coupon.code}",
        reference=str(coupon.id),
        idempotency_key=f"coupon-ledger:{payload.idempotency_key}",
    )
    tx.metadata_json = {**(tx.metadata_json or {}), "coupon_id": str(coupon.id), "benefit": benefit}
    redemption = CouponRedemption(
        brand_id=customer.brand_id,
        coupon_id=coupon.id,
        customer_id=customer.id,
        actor_id=user.id,
        branch_id=branch_id,
        benefit=benefit,
        idempotency_key=payload.idempotency_key,
    )
    coupon.redemption_count += 1
    db.add(redemption)
    add_audit(
        db,
        actor_id=user.id,
        action="coupon_redeemed",
        entity_type="coupon",
        entity_id=coupon.id,
        brand_id=customer.brand_id,
        details={"customer_id": str(customer.id), "code": coupon.code, "benefit": benefit},
        ip_address=request.client.host if request.client else None,
    )
    wallet_pass = await db.scalar(
        select(WalletPass).where(WalletPass.customer_id == customer.id, WalletPass.status == "active")
    )
    if wallet_pass and (points or stamps):
        wallet_pass.update_tag += 1
    await db.commit()
    await db.refresh(customer)
    if wallet_pass and (points or stamps):
        await push_pass_update(db, wallet_pass)
        await db.commit()
    return {"customer": customer_out(customer), "benefit": benefit, "duplicate": False}


@router.post("/transactions/{transaction_id}/reverse")
async def reverse_transaction(
    transaction_id: uuid.UUID,
    payload: TransactionReverse,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(current_user),
):
    original = await db.scalar(
        select(LoyaltyTransaction).where(LoyaltyTransaction.id == transaction_id).with_for_update()
    )
    if not original:
        raise HTTPException(404, "عملية الولاء غير موجودة")
    await brand_access(db, user, original.brand_id, permission="loyalty.manage")
    if original.action in {"reversal", "points_expired"}:
        raise HTTPException(400, "لا يمكن عكس هذه العملية")
    duplicate = await db.scalar(
        select(LoyaltyTransaction).where(LoyaltyTransaction.idempotency_key == payload.idempotency_key)
    )
    if duplicate:
        customer = await db.get(Customer, original.customer_id)
        return {"customer": customer_out(customer), "transaction": transaction_out(duplicate), "duplicate": True}
    already = await db.scalar(
        select(LoyaltyTransaction).where(
            LoyaltyTransaction.action == "reversal",
            LoyaltyTransaction.reference == f"reversal:{original.id}",
        )
    )
    if already:
        raise HTTPException(409, "تم عكس هذه العملية مسبقًا")
    customer = await db.scalar(
        select(Customer).where(Customer.id == original.customer_id).with_for_update()
    )
    if not customer:
        raise HTTPException(404, "العميل غير موجود")

    metadata = original.metadata_json or {}
    points_effect = original.points_after - original.points_before
    stamps_effect = original.stamps_after - original.stamps_before
    rewards_effect = int(metadata.get("stamp_rewards", 0) or 0) + int(metadata.get("point_rewards", 0) or 0)
    if points_effect > customer.points:
        raise HTTPException(409, "لا يمكن عكس العملية لأن العميل استخدم جزءًا من النقاط المكتسبة")
    if stamps_effect > customer.stamps:
        raise HTTPException(409, "لا يمكن عكس العملية لأن العميل استخدم الأختام المكتسبة")
    if rewards_effect > customer.available_rewards:
        raise HTTPException(409, "لا يمكن عكس العملية لأن المكافأة الناتجة تم استخدامها")

    points_before = customer.points
    stamps_before = customer.stamps
    customer.points -= points_effect
    customer.stamps -= stamps_effect
    customer.available_rewards -= rewards_effect
    if points_effect > 0:
        await consume_point_buckets(db, customer.id, points_effect)
    if original.action in {"visit", "spend"}:
        customer.visits = max(0, customer.visits - 1)
    if original.action == "spend":
        customer.total_spend = max(Decimal("0"), Decimal(customer.total_spend or 0) - Decimal(original.amount or 0))
    if original.action == "redeem_earned":
        customer.available_rewards += 1
    if original.action == "redeem_reward":
        reward_id = metadata.get("reward_id")
        if reward_id:
            reward = await db.get(Reward, uuid.UUID(str(reward_id)))
            if reward and reward.stock is not None:
                reward.stock += 1
    await recalculate_tier(db, customer)
    reversal = LoyaltyTransaction(
        brand_id=original.brand_id,
        branch_id=original.branch_id,
        customer_id=original.customer_id,
        actor_id=user.id,
        action="reversal",
        delta_points=customer.points - points_before,
        delta_stamps=customer.stamps - stamps_before,
        points_before=points_before,
        points_after=customer.points,
        stamps_before=stamps_before,
        stamps_after=customer.stamps,
        amount=-Decimal(original.amount or 0),
        reference=f"reversal:{original.id}",
        idempotency_key=payload.idempotency_key,
        metadata_json={"original_transaction_id": str(original.id), "reason": payload.reason},
    )
    db.add(reversal)
    add_audit(
        db,
        actor_id=user.id,
        action="loyalty_transaction_reversed",
        entity_type="loyalty_transaction",
        entity_id=original.id,
        brand_id=original.brand_id,
        details={"reason": payload.reason, "reversal_id": str(reversal.id)},
        ip_address=request.client.host if request.client else None,
    )
    wallet_pass = await db.scalar(
        select(WalletPass).where(WalletPass.customer_id == customer.id, WalletPass.status == "active")
    )
    if wallet_pass:
        wallet_pass.update_tag += 1
    await db.commit()
    await db.refresh(reversal)
    await db.refresh(customer)
    if wallet_pass:
        await push_pass_update(db, wallet_pass)
        await db.commit()
    return {"customer": customer_out(customer), "transaction": transaction_out(reversal), "duplicate": False}
