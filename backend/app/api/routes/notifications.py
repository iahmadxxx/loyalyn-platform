import secrets
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import brand_access, current_user
from app.db.session import get_db
from app.models import Branch, Customer, Notification, NotificationCampaign, NotificationRecipient, NotificationTemplate
from app.schemas.common import CampaignCreate, CampaignUpdate, NotificationTemplateCreate
from app.services.audit import add_audit

router = APIRouter()


async def validate_audience(
    db: AsyncSession, brand_id: uuid.UUID, audience_type: str, audience_filter: dict | None
) -> dict:
    filters = dict(audience_filter or {})
    if audience_type == "branch":
        raw = filters.get("branch_id")
        if not raw:
            raise HTTPException(422, "اختر الفرع المستهدف")
        try:
            branch_id = uuid.UUID(str(raw))
        except ValueError as exc:
            raise HTTPException(422, "معرف الفرع غير صحيح") from exc
        branch = await db.get(Branch, branch_id)
        if not branch or branch.brand_id != brand_id or not branch.is_active:
            raise HTTPException(422, "الفرع المستهدف غير موجود داخل هذا البراند أو أنه موقوف")
        filters["branch_id"] = str(branch_id)
    elif audience_type == "selected":
        raw_ids = filters.get("customer_ids") or []
        if not isinstance(raw_ids, list) or not raw_ids:
            raise HTTPException(422, "اختر عميلًا واحدًا على الأقل")
        try:
            customer_ids = list(dict.fromkeys(uuid.UUID(str(value)) for value in raw_ids))
        except ValueError as exc:
            raise HTTPException(422, "قائمة العملاء تحتوي على معرف غير صحيح") from exc
        found = list((await db.scalars(
            select(Customer.id).where(
                Customer.brand_id == brand_id, Customer.id.in_(customer_ids), Customer.is_active.is_(True)
            )
        )).all())
        if len(found) != len(customer_ids):
            raise HTTPException(422, "أحد العملاء المحددين لا ينتمي إلى هذا البراند أو أنه موقوف")
        filters["customer_ids"] = [str(value) for value in customer_ids]
    elif audience_type == "tier" and not str(filters.get("tier", "")).strip():
        raise HTTPException(422, "اكتب اسم مستوى العضوية المستهدف")
    return filters


def campaign_out(x: NotificationCampaign) -> dict:
    return {
        "id": str(x.id), "brand_id": str(x.brand_id), "name": x.name,
        "title": x.title, "body": x.body, "channel": x.channel,
        "audience_type": x.audience_type, "audience_filter": x.audience_filter or {},
        "recurrence": x.recurrence, "series_key": x.series_key,
        "status": x.status, "scheduled_at": x.scheduled_at, "started_at": x.started_at,
        "completed_at": x.completed_at, "total_recipients": x.total_recipients,
        "sent_count": x.sent_count, "failed_count": x.failed_count,
        "skipped_count": x.skipped_count, "created_at": x.created_at,
    }


@router.get("/templates")
async def list_templates(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, brand_id, permission="campaigns.view")
    rows = list((await db.scalars(select(NotificationTemplate).where(NotificationTemplate.brand_id == brand_id).order_by(NotificationTemplate.created_at.desc()))).all())
    return [{"id": str(x.id), "name": x.name, "title": x.title, "body": x.body, "channel": x.channel, "is_active": x.is_active} for x in rows]


@router.post("/templates", status_code=201)
async def create_template(payload: NotificationTemplateCreate, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, payload.brand_id, permission="campaigns.manage")
    template = NotificationTemplate(**payload.model_dump())
    db.add(template)
    await db.flush()
    add_audit(db, actor_id=user.id, action="notification_template_created", entity_type="notification_template", entity_id=template.id, brand_id=payload.brand_id, details={"name": template.name}, ip_address=request.client.host if request.client else None)
    await db.commit()
    await db.refresh(template)
    return {"id": str(template.id)}


@router.patch("/templates/{template_id}/toggle")
async def toggle_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    template = await db.get(NotificationTemplate, template_id)
    if not template:
        raise HTTPException(404, "القالب غير موجود")
    await brand_access(db, user, template.brand_id, permission="campaigns.manage")
    template.is_active = not template.is_active
    await db.commit()
    return {"ok": True, "is_active": template.is_active}


@router.get("/campaigns")
async def list_campaigns(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, brand_id, permission="campaigns.view")
    rows = list((await db.scalars(select(NotificationCampaign).where(NotificationCampaign.brand_id == brand_id).order_by(NotificationCampaign.created_at.desc()).limit(300))).all())
    return [campaign_out(x) for x in rows]


@router.post("/campaigns", status_code=201)
async def create_campaign(payload: CampaignCreate, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    await brand_access(db, user, payload.brand_id, permission="campaigns.manage")
    audience_filter = await validate_audience(
        db, payload.brand_id, payload.audience_type, payload.audience_filter
    )
    now = datetime.now(timezone.utc)
    if payload.send_now:
        status = "queued"
        scheduled_at = now
    elif payload.scheduled_at:
        status = "scheduled"
        scheduled_at = payload.scheduled_at
    else:
        status = "draft"
        scheduled_at = None
    campaign = NotificationCampaign(
        brand_id=payload.brand_id, created_by=user.id, name=payload.name,
        title=payload.title, body=payload.body, channel=payload.channel,
        audience_type=payload.audience_type, audience_filter=audience_filter,
        recurrence=payload.recurrence, series_key=secrets.token_hex(10) if payload.recurrence != "none" else None,
        status=status, scheduled_at=scheduled_at,
    )
    db.add(campaign)
    await db.flush()
    add_audit(db, actor_id=user.id, action="campaign_created", entity_type="notification_campaign", entity_id=campaign.id, brand_id=payload.brand_id, details={"channel": campaign.channel, "audience_type": campaign.audience_type, "status": campaign.status}, ip_address=request.client.host if request.client else None)
    await db.commit()
    await db.refresh(campaign)
    return campaign_out(campaign)


@router.patch("/campaigns/{campaign_id}")
async def update_campaign(campaign_id: uuid.UUID, payload: CampaignUpdate, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    campaign = await db.get(NotificationCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "الحملة غير موجودة")
    await brand_access(db, user, campaign.brand_id, permission="campaigns.manage")
    if campaign.status not in {"draft", "scheduled"}:
        raise HTTPException(409, "لا يمكن تعديل حملة بدأ إرسالها")
    data = payload.model_dump(exclude_unset=True)
    next_audience_type = data.get("audience_type", campaign.audience_type)
    next_audience_filter = data.get("audience_filter", campaign.audience_filter or {})
    if "audience_type" in data or "audience_filter" in data:
        data["audience_filter"] = await validate_audience(
            db, campaign.brand_id, next_audience_type, next_audience_filter
        )
    for field, value in data.items():
        setattr(campaign, field, value)
    if campaign.scheduled_at:
        campaign.status = "scheduled"
    add_audit(db, actor_id=user.id, action="campaign_updated", entity_type="notification_campaign", entity_id=campaign.id, brand_id=campaign.brand_id, details=data, ip_address=request.client.host if request.client else None)
    await db.commit()
    await db.refresh(campaign)
    return campaign_out(campaign)


@router.post("/campaigns/{campaign_id}/send")
async def send_campaign(campaign_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    campaign = await db.get(NotificationCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "الحملة غير موجودة")
    await brand_access(db, user, campaign.brand_id, permission="campaigns.manage")
    if campaign.status in {"processing", "completed", "cancelled"}:
        raise HTTPException(409, "حالة الحملة لا تسمح بالإرسال")
    if campaign.status in {"failed", "partially_completed"}:
        failed_rows = list((await db.scalars(select(NotificationRecipient).where(NotificationRecipient.campaign_id == campaign.id, NotificationRecipient.status == "failed"))).all())
        for recipient in failed_rows:
            recipient.status = "pending"
            recipient.error = None
            recipient.attempts = 0
        campaign.failed_count = 0
        campaign.completed_at = None
    campaign.status = "queued"
    campaign.scheduled_at = datetime.now(timezone.utc)
    add_audit(db, actor_id=user.id, action="campaign_queued", entity_type="notification_campaign", entity_id=campaign.id, brand_id=campaign.brand_id, ip_address=request.client.host if request.client else None)
    await db.commit()
    await db.refresh(campaign)
    return campaign_out(campaign)


@router.post("/campaigns/{campaign_id}/cancel")
async def cancel_campaign(campaign_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    campaign = await db.get(NotificationCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "الحملة غير موجودة")
    await brand_access(db, user, campaign.brand_id, permission="campaigns.manage")
    if campaign.status in {"completed", "partially_completed", "cancelled"}:
        return campaign_out(campaign)
    campaign.status = "cancelled"
    add_audit(db, actor_id=user.id, action="campaign_cancelled", entity_type="notification_campaign", entity_id=campaign.id, brand_id=campaign.brand_id, ip_address=request.client.host if request.client else None)
    await db.commit()
    return campaign_out(campaign)


@router.get("/campaigns/{campaign_id}/recipients")
async def campaign_recipients(campaign_id: uuid.UUID, db: AsyncSession = Depends(get_db), user=Depends(current_user)):
    campaign = await db.get(NotificationCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "الحملة غير موجودة")
    await brand_access(db, user, campaign.brand_id, permission="campaigns.view")
    rows = (await db.execute(
        select(NotificationRecipient, Customer)
        .join(Customer, Customer.id == NotificationRecipient.customer_id)
        .where(NotificationRecipient.campaign_id == campaign_id)
        .order_by(NotificationRecipient.created_at.asc())
    )).all()
    return [{"id": str(r.id), "customer_id": str(c.id), "customer_name": c.name, "status": r.status, "attempts": r.attempts, "error": r.error, "sent_at": r.sent_at} for r, c in rows]


@router.get("/inbox/{membership_code}")
async def customer_inbox(membership_code: str, db: AsyncSession = Depends(get_db)):
    customer = await db.scalar(select(Customer).where(Customer.membership_code == membership_code, Customer.is_active.is_(True)))
    if not customer:
        return []
    rows = list((await db.scalars(select(Notification).where(Notification.customer_id == customer.id, Notification.status == "sent").order_by(Notification.created_at.desc()).limit(100))).all())
    return [{"id": str(x.id), "title": x.title, "body": x.body, "is_read": x.is_read, "created_at": x.created_at} for x in rows]
