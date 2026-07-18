from datetime import datetime, timedelta, timezone
import uuid
import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.models import (
    Customer, Notification, NotificationCampaign, NotificationRecipient, WalletPass,
)
from app.services.wallet import push_pass_update

settings = get_settings()


async def audience_customers(db: AsyncSession, campaign: NotificationCampaign) -> list[Customer]:
    query = select(Customer).where(Customer.brand_id == campaign.brand_id, Customer.is_active.is_(True))
    filters = campaign.audience_filter or {}
    if campaign.audience_type == "tier":
        query = query.where(Customer.tier == str(filters.get("tier", "")))
    elif campaign.audience_type == "min_points":
        query = query.where(Customer.points >= int(filters.get("min_points", 0)))
    elif campaign.audience_type == "inactive_days":
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, int(filters.get("days", 30))))
        query = query.where((Customer.last_visit_at.is_(None)) | (Customer.last_visit_at <= cutoff))
    elif campaign.audience_type == "birthday":
        today = datetime.now(timezone.utc).date()
        query = query.where(func.extract("month", Customer.birthday) == today.month, func.extract("day", Customer.birthday) == today.day)
    elif campaign.audience_type == "selected":
        ids = [uuid.UUID(str(value)) for value in (filters.get("customer_ids") or [])]
        query = query.where(Customer.id.in_(ids))
    elif campaign.audience_type == "branch":
        raw_branch_id = filters.get("branch_id")
        if raw_branch_id:
            query = query.where(Customer.home_branch_id == uuid.UUID(str(raw_branch_id)))
        else:
            query = query.where(Customer.id.is_(None))
    elif campaign.audience_type == "rewards_ready":
        query = query.where(Customer.available_rewards > 0)
    return list((await db.scalars(query.order_by(Customer.created_at.asc()))).all())


async def ensure_recipients(db: AsyncSession, campaign: NotificationCampaign) -> list[NotificationRecipient]:
    existing = list((await db.scalars(select(NotificationRecipient).where(NotificationRecipient.campaign_id == campaign.id))).all())
    if existing:
        return existing
    customers = await audience_customers(db, campaign)
    recipients = [NotificationRecipient(campaign_id=campaign.id, customer_id=c.id) for c in customers]
    db.add_all(recipients)
    campaign.total_recipients = len(recipients)
    await db.flush()
    return recipients


async def _provider_send(url: str, payload: dict) -> tuple[bool, str | None]:
    if not url:
        return False, "provider_not_configured"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, json=payload)
            if 200 <= response.status_code < 300:
                return True, response.headers.get("x-message-id")
            return False, f"provider_http_{response.status_code}"
    except Exception as exc:
        return False, str(exc)[:500]


async def process_campaign(db: AsyncSession, campaign: NotificationCampaign) -> NotificationCampaign:
    # Claim the campaign row atomically. This prevents the API and worker (or two
    # worker processes) from delivering the same campaign at the same time.
    locked = await db.scalar(
        select(NotificationCampaign)
        .where(NotificationCampaign.id == campaign.id)
        .with_for_update()
    )
    if not locked:
        return campaign
    campaign = locked
    if campaign.status in {"completed", "cancelled", "processing"}:
        return campaign
    campaign.status = "processing"
    campaign.started_at = datetime.now(timezone.utc)
    recipients = await ensure_recipients(db, campaign)
    await db.commit()

    for recipient in recipients:
        # A platform/brand administrator may cancel while a large campaign is
        # being delivered. Re-read the status before every recipient so the
        # worker stops cleanly instead of continuing with a stale ORM object.
        current_status = await db.scalar(
            select(NotificationCampaign.status).where(NotificationCampaign.id == campaign.id)
        )
        if current_status == "cancelled":
            break
        if recipient.status in {"sent", "skipped", "failed"}:
            continue
        customer = await db.get(Customer, recipient.customer_id)
        if not customer or not customer.is_active:
            recipient.status = "skipped"
            recipient.error = "customer_unavailable"
            campaign.skipped_count += 1
            continue
        recipient.attempts += 1
        payload = {
            "brand_id": str(campaign.brand_id),
            "customer_id": str(customer.id),
            "customer_name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "title": campaign.title,
            "body": campaign.body,
            "campaign_id": str(campaign.id),
        }
        ok = False
        message_id = None
        error = None
        if campaign.channel == "in_app":
            db.add(Notification(
                brand_id=campaign.brand_id,
                customer_id=customer.id,
                campaign_id=campaign.id,
                title=campaign.title,
                body=campaign.body,
                channel="in_app",
                audience=campaign.audience_type,
                status="sent",
                sent_at=datetime.now(timezone.utc),
            ))
            ok = True
        elif campaign.channel == "wallet_push":
            wallet_pass = await db.scalar(select(WalletPass).where(WalletPass.customer_id == customer.id, WalletPass.status == "active"))
            if wallet_pass:
                wallet_pass.update_tag += 1
                result = await push_pass_update(db, wallet_pass)
                ok = result.get("failed", 0) == 0 and result.get("reason") is None
                error = result.get("reason") or (None if ok else "wallet_push_failed")
            else:
                error = "customer_has_no_wallet_pass"
        elif campaign.channel == "email":
            ok, message_id = await _provider_send(settings.smtp_webhook_url, payload)
            if not ok:
                error = message_id
        elif campaign.channel == "sms":
            ok, message_id = await _provider_send(settings.sms_webhook_url, payload)
            if not ok:
                error = message_id
        else:
            ok, message_id = await _provider_send(settings.notification_webhook_url, payload)
            if not ok:
                error = message_id
        if ok:
            recipient.status = "sent"
            recipient.sent_at = datetime.now(timezone.utc)
            recipient.provider_message_id = message_id
            campaign.sent_count += 1
        else:
            recipient.status = "failed" if recipient.attempts >= 3 else "pending"
            recipient.error = error or "delivery_failed"
            if recipient.status == "failed":
                campaign.failed_count += 1
        await db.commit()

    await db.refresh(campaign)
    if campaign.status == "cancelled":
        pending_rows = list((await db.scalars(
            select(NotificationRecipient).where(
                NotificationRecipient.campaign_id == campaign.id,
                NotificationRecipient.status == "pending",
            )
        )).all())
        for pending_recipient in pending_rows:
            pending_recipient.status = "skipped"
            pending_recipient.error = "campaign_cancelled"
        campaign.skipped_count += len(pending_rows)
        campaign.completed_at = datetime.now(timezone.utc)
        await db.commit()
        return campaign

    pending = await db.scalar(select(func.count()).select_from(NotificationRecipient).where(NotificationRecipient.campaign_id == campaign.id, NotificationRecipient.status == "pending"))
    if pending:
        campaign.status = "queued"
    else:
        if campaign.failed_count and campaign.sent_count:
            campaign.status = "partially_completed"
        elif campaign.failed_count:
            campaign.status = "failed"
        else:
            campaign.status = "completed"
        campaign.completed_at = datetime.now(timezone.utc)
        if campaign.status in {"completed", "partially_completed"} and campaign.recurrence in {"daily", "weekly", "monthly"}:
            base = campaign.scheduled_at or campaign.started_at or datetime.now(timezone.utc)
            if campaign.recurrence == "daily":
                next_at = base + timedelta(days=1)
            elif campaign.recurrence == "weekly":
                next_at = base + timedelta(days=7)
            else:
                next_at = base + timedelta(days=30)
            db.add(NotificationCampaign(
                brand_id=campaign.brand_id, created_by=campaign.created_by, name=campaign.name,
                title=campaign.title, body=campaign.body, channel=campaign.channel,
                audience_type=campaign.audience_type, audience_filter=campaign.audience_filter or {},
                recurrence=campaign.recurrence, series_key=campaign.series_key,
                status="scheduled", scheduled_at=next_at,
            ))
    await db.commit()
    return campaign


async def process_due_campaigns(db: AsyncSession) -> int:
    now = datetime.now(timezone.utc)
    campaigns = list((await db.scalars(
        select(NotificationCampaign).where(
            NotificationCampaign.status.in_(["queued", "scheduled"]),
            (NotificationCampaign.scheduled_at.is_(None)) | (NotificationCampaign.scheduled_at <= now),
        ).order_by(NotificationCampaign.created_at.asc()).limit(20)
    )).all())
    for campaign in campaigns:
        await process_campaign(db, campaign)
    return len(campaigns)
