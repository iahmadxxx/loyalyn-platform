from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Customer, LoyaltyProgram, LoyaltyTransaction, MembershipTier, WalletPass


def program_dict(program: LoyaltyProgram) -> dict:
    return {
        "id": str(program.id),
        "brand_id": str(program.brand_id),
        "enabled": program.enabled,
        "program_type": program.program_type,
        "points_per_visit": program.points_per_visit,
        "points_per_currency": program.points_per_currency,
        "required_stamps": program.required_stamps,
        "stamp_reward_title": program.stamp_reward_title,
        "reward_points": program.reward_points,
        "reward_title": program.reward_title,
        "birthday_bonus": program.birthday_bonus,
        "referral_bonus": program.referral_bonus,
        "cashback_percent": program.cashback_percent,
        "points_expiry_days": program.points_expiry_days,
        "daily_points_cap": program.daily_points_cap,
        "allow_manual_adjustment": program.allow_manual_adjustment,
        "rules": program.rules or {},
    }


def calculate_deltas(
    program: LoyaltyProgram,
    action: str,
    amount: Decimal,
    points: int,
    stamps: int,
) -> tuple[int, int]:
    if not program.enabled:
        return 0, 0
    if action == "visit":
        return (
            program.points_per_visit if program.program_type in {"points", "hybrid"} else 0,
            1 if program.program_type in {"stamps", "hybrid"} else 0,
        )
    if action == "spend":
        calculated = int(amount * program.points_per_currency) if program.program_type in {"points", "hybrid"} else 0
        if program.program_type == "cashback":
            calculated = int(amount * Decimal(program.cashback_percent) / Decimal(100))
        return calculated, 0
    if action == "birthday":
        return program.birthday_bonus, 0
    if action == "referral":
        return program.referral_bonus, 0
    if action in {"manual", "reversal", "coupon"}:
        if action == "manual" and not program.allow_manual_adjustment:
            raise ValueError("التعديلات اليدوية متوقفة في إعدادات برنامج الولاء")
        return points, stamps
    raise ValueError("نوع عملية الولاء غير مدعوم")


def _safe_multiplier(value: Any, default: Decimal = Decimal("1")) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return min(parsed, Decimal("20"))


def _time_in_window(now_time: time, start: str, end: str) -> bool:
    try:
        start_time = time.fromisoformat(start)
        end_time = time.fromisoformat(end)
    except (TypeError, ValueError):
        return False
    if start_time <= end_time:
        return start_time <= now_time <= end_time
    return now_time >= start_time or now_time <= end_time


async def effective_points_multiplier(
    db: AsyncSession,
    customer: Customer,
    program: LoyaltyProgram,
    *,
    action: str,
    branch_id,
) -> Decimal:
    """Resolve tier and time/branch multipliers without trusting client input.

    Supported `program.rules` keys:
      - global_multiplier: number
      - weekday_multipliers: {"0": 2, ...}, Monday is 0
      - branch_multipliers: {"<branch uuid>": 2}
      - happy_hours: [{"start":"14:00", "end":"17:00", "multiplier":2}]
    """
    if action not in {"visit", "spend"}:
        return Decimal("1")

    multiplier = Decimal("1")
    tier = await db.scalar(
        select(MembershipTier).where(
            MembershipTier.brand_id == customer.brand_id,
            MembershipTier.name == customer.tier,
            MembershipTier.is_active.is_(True),
        )
    )
    if tier:
        multiplier *= _safe_multiplier(tier.points_multiplier)

    rules = program.rules or {}
    multiplier *= _safe_multiplier(rules.get("global_multiplier", 1))

    now = datetime.now(timezone.utc)
    weekday_map = rules.get("weekday_multipliers") or {}
    multiplier *= _safe_multiplier(weekday_map.get(str(now.weekday()), 1))

    if branch_id:
        branch_map = rules.get("branch_multipliers") or {}
        multiplier *= _safe_multiplier(branch_map.get(str(branch_id), 1))

    for window in rules.get("happy_hours") or []:
        if isinstance(window, dict) and _time_in_window(now.time(), str(window.get("start", "")), str(window.get("end", ""))):
            multiplier *= _safe_multiplier(window.get("multiplier", 1))

    return min(multiplier, Decimal("100"))


async def enforce_daily_cap(
    db: AsyncSession,
    customer: Customer,
    program: LoyaltyProgram,
    delta_points: int,
) -> int:
    if not program.daily_points_cap or delta_points <= 0:
        return delta_points
    now = datetime.now(timezone.utc)
    start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    earned_today = await db.scalar(
        select(func.coalesce(func.sum(LoyaltyTransaction.delta_points), 0)).where(
            LoyaltyTransaction.customer_id == customer.id,
            LoyaltyTransaction.created_at >= start,
            LoyaltyTransaction.delta_points > 0,
            LoyaltyTransaction.action != "reversal",
        )
    )
    remaining = max(0, program.daily_points_cap - int(earned_today or 0))
    return min(delta_points, remaining)


async def recalculate_tier(db: AsyncSession, customer: Customer) -> None:
    tiers = (
        await db.scalars(
            select(MembershipTier)
            .where(
                MembershipTier.brand_id == customer.brand_id,
                MembershipTier.is_active.is_(True),
            )
            .order_by(MembershipTier.rank.asc())
        )
    ).all()
    selected = None
    for tier in tiers:
        if customer.points >= tier.min_points and Decimal(customer.total_spend or 0) >= Decimal(tier.min_spend):
            selected = tier
    if selected:
        customer.tier = selected.name


async def consume_point_buckets(db: AsyncSession, customer_id, points: int) -> int:
    """Consume expiring point buckets FIFO. Legacy points have no bucket and remain usable."""
    remaining = max(0, int(points))
    if not remaining:
        return 0
    buckets = list(
        (
            await db.scalars(
                select(LoyaltyTransaction)
                .where(
                    LoyaltyTransaction.customer_id == customer_id,
                    LoyaltyTransaction.remaining_points > 0,
                )
                .order_by(
                    LoyaltyTransaction.expires_at.asc().nullslast(),
                    LoyaltyTransaction.created_at.asc(),
                )
            )
        ).all()
    )
    consumed = 0
    for bucket in buckets:
        if remaining <= 0:
            break
        take = min(remaining, max(0, bucket.remaining_points))
        bucket.remaining_points -= take
        remaining -= take
        consumed += take
    return consumed


async def apply_loyalty(
    db: AsyncSession,
    customer: Customer,
    program: LoyaltyProgram,
    *,
    actor_id,
    action: str,
    branch_id,
    amount: Decimal,
    points: int,
    stamps: int,
    note: str | None,
    reference: str | None,
    idempotency_key: str,
) -> tuple[LoyaltyTransaction, bool]:
    existing = await db.scalar(
        select(LoyaltyTransaction).where(LoyaltyTransaction.idempotency_key == idempotency_key)
    )
    if existing:
        return existing, True

    delta_points, delta_stamps = calculate_deltas(program, action, amount, points, stamps)
    if delta_points > 0:
        multiplier = await effective_points_multiplier(
            db, customer, program, action=action, branch_id=branch_id
        )
        delta_points = int(Decimal(delta_points) * multiplier)
    else:
        multiplier = Decimal("1")
    delta_points = await enforce_daily_cap(db, customer, program, delta_points)

    points_before = customer.points
    stamps_before = customer.stamps
    requested_points_after = customer.points + delta_points
    requested_stamps_after = customer.stamps + delta_stamps
    customer.points = max(0, requested_points_after)
    customer.stamps = max(0, requested_stamps_after)
    effective_delta_points = customer.points - points_before
    effective_delta_stamps = customer.stamps - stamps_before

    if effective_delta_points < 0:
        await consume_point_buckets(db, customer.id, -effective_delta_points)

    if action in {"visit", "spend"}:
        customer.visits += 1
        customer.last_visit_at = datetime.now(timezone.utc)
    if action == "spend":
        customer.total_spend = Decimal(customer.total_spend or 0) + amount

    stamp_rewards = 0
    if program.program_type in {"stamps", "hybrid"} and program.required_stamps > 0:
        stamp_rewards = customer.stamps // program.required_stamps
        if stamp_rewards:
            customer.stamps %= program.required_stamps
            customer.available_rewards += stamp_rewards

    point_rewards = 0
    auto_convert = bool((program.rules or {}).get("auto_convert_points", False))
    if auto_convert and program.reward_points > 0:
        point_rewards = customer.points // program.reward_points
        if point_rewards:
            consumed_for_rewards = point_rewards * program.reward_points
            customer.points %= program.reward_points
            await consume_point_buckets(db, customer.id, consumed_for_rewards)
            customer.available_rewards += point_rewards

    await recalculate_tier(db, customer)
    retained_points = max(0, customer.points - points_before)
    expires_at = None
    if retained_points and program.points_expiry_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=program.points_expiry_days)

    transaction = LoyaltyTransaction(
        brand_id=customer.brand_id,
        branch_id=branch_id,
        customer_id=customer.id,
        actor_id=actor_id,
        action=action,
        delta_points=effective_delta_points,
        delta_stamps=effective_delta_stamps,
        points_before=points_before,
        points_after=customer.points,
        stamps_before=stamps_before,
        stamps_after=customer.stamps,
        amount=amount,
        reference=reference,
        idempotency_key=idempotency_key,
        expires_at=expires_at,
        remaining_points=retained_points,
        metadata_json={
            "note": note or "",
            "stamp_rewards": stamp_rewards,
            "point_rewards": point_rewards,
            "multiplier": str(multiplier),
        },
    )
    db.add(transaction)
    return transaction, False


async def process_expired_points(db: AsyncSession, *, limit: int = 200) -> int:
    now = datetime.now(timezone.utc)
    buckets = list(
        (
            await db.scalars(
                select(LoyaltyTransaction)
                .where(
                    LoyaltyTransaction.remaining_points > 0,
                    LoyaltyTransaction.expires_at.is_not(None),
                    LoyaltyTransaction.expires_at <= now,
                )
                .order_by(LoyaltyTransaction.expires_at.asc())
                .limit(limit)
            )
        ).all()
    )
    changed_passes: list[WalletPass] = []
    processed = 0
    for bucket in buckets:
        customer = await db.get(Customer, bucket.customer_id)
        remaining = max(0, bucket.remaining_points)
        bucket.remaining_points = 0
        if not customer or remaining <= 0:
            continue
        expired = min(remaining, max(0, customer.points))
        if expired <= 0:
            continue
        before = customer.points
        customer.points -= expired
        await recalculate_tier(db, customer)
        db.add(
            LoyaltyTransaction(
                brand_id=customer.brand_id,
                customer_id=customer.id,
                action="points_expired",
                delta_points=-expired,
                points_before=before,
                points_after=customer.points,
                stamps_before=customer.stamps,
                stamps_after=customer.stamps,
                amount=Decimal("0"),
                reference=f"expiry:{bucket.id}",
                idempotency_key=f"expiry:{bucket.id}",
                remaining_points=0,
                metadata_json={"source_transaction_id": str(bucket.id)},
            )
        )
        wallet_pass = await db.scalar(
            select(WalletPass).where(
                WalletPass.customer_id == customer.id,
                WalletPass.status == "active",
            )
        )
        if wallet_pass:
            wallet_pass.update_tag += 1
            changed_passes.append(wallet_pass)
        processed += 1
    await db.commit()

    if changed_passes:
        from app.services.wallet import push_pass_update

        for wallet_pass in changed_passes:
            await push_pass_update(db, wallet_pass)
        await db.commit()
    return processed


async def process_birthday_bonuses(db: AsyncSession, *, limit: int = 500) -> int:
    today = datetime.now(timezone.utc).date()
    customers = list(
        (
            await db.scalars(
                select(Customer)
                .where(
                    Customer.is_active.is_(True),
                    Customer.birthday.is_not(None),
                    func.extract("month", Customer.birthday) == today.month,
                    func.extract("day", Customer.birthday) == today.day,
                )
                .limit(limit)
            )
        ).all()
    )
    processed = 0
    for customer in customers:
        program = await db.scalar(
            select(LoyaltyProgram).where(LoyaltyProgram.brand_id == customer.brand_id)
        )
        if not program or not program.enabled or program.birthday_bonus <= 0:
            continue
        key = f"birthday:{customer.id}:{today.year}"
        _, duplicate = await apply_loyalty(
            db,
            customer,
            program,
            actor_id=None,
            action="birthday",
            branch_id=None,
            amount=Decimal("0"),
            points=0,
            stamps=0,
            note="مكافأة عيد الميلاد التلقائية",
            reference=str(today.year),
            idempotency_key=key,
        )
        if not duplicate:
            wallet_pass = await db.scalar(
                select(WalletPass).where(
                    WalletPass.customer_id == customer.id,
                    WalletPass.status == "active",
                )
            )
            if wallet_pass:
                wallet_pass.update_tag += 1
            processed += 1
    await db.commit()
    return processed
