from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Customer, LoyaltyProgram, LoyaltyTransaction

async def add_stamp(db: AsyncSession, customer: Customer, branch_id, actor_id, idempotency_key: str):
    duplicate = await db.scalar(select(LoyaltyTransaction).where(
        LoyaltyTransaction.customer_id == customer.id,
        LoyaltyTransaction.metadata_json["idempotency_key"].as_string() == idempotency_key,
    ))
    if duplicate:
        return customer, duplicate, False

    program = await db.scalar(select(LoyaltyProgram).where(LoyaltyProgram.brand_id == customer.brand_id))
    required = program.required_stamps if program else 6
    customer.stamps += 1
    if customer.stamps >= required:
        customer.available_rewards += 1
        customer.stamps = 0

    tx = LoyaltyTransaction(
        brand_id=customer.brand_id,
        branch_id=branch_id,
        customer_id=customer.id,
        actor_id=actor_id,
        action="stamp_added",
        delta_stamps=1,
        metadata_json={"idempotency_key": idempotency_key},
    )
    db.add(tx)
    await db.commit()
    await db.refresh(customer)
    return customer, tx, True
