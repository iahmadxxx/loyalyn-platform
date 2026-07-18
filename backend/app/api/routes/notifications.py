from datetime import datetime,timezone
import httpx
from fastapi import APIRouter,Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models import Notification,Customer
from app.schemas.common import NotificationCreate
from app.api.deps import current_user,allow
from app.core.config import get_settings
router=APIRouter(); settings=get_settings()
@router.get('')
async def list_all(brand_id:str|None=None,db:AsyncSession=Depends(get_db),u=Depends(current_user)):
 q=select(Notification).order_by(Notification.created_at.desc()).limit(300)
 if u.brand_id:q=q.where(Notification.brand_id==u.brand_id)
 elif brand_id:q=q.where(Notification.brand_id==brand_id)
 rows=(await db.scalars(q)).all(); return [{'id':str(x.id),'brand_id':str(x.brand_id),'customer_id':str(x.customer_id) if x.customer_id else None,'title':x.title,'body':x.body,'channel':x.channel,'audience':x.audience,'status':x.status,'scheduled_at':x.scheduled_at,'sent_at':x.sent_at,'created_at':x.created_at} for x in rows]
@router.post('',status_code=201)
async def send(p:NotificationCreate,db:AsyncSession=Depends(get_db),u=Depends(allow('owner','admin','manager'))):
 now=datetime.now(timezone.utc); status='scheduled' if p.scheduled_at and p.scheduled_at>now else 'sent'
 targets=[p.customer_id] if p.customer_id else [x for x in (await db.scalars(select(Customer.id).where(Customer.brand_id==p.brand_id,Customer.is_active==True))).all()]
 count=0
 for cid in targets:
  db.add(Notification(**p.model_dump(),customer_id=cid,audience='individual' if p.customer_id else p.audience,status=status,sent_at=now if status=='sent' else None)); count+=1
 await db.commit()
 if settings.notification_webhook_url and status=='sent':
  try:
   async with httpx.AsyncClient(timeout=10) as client: await client.post(settings.notification_webhook_url,json={'brand_id':str(p.brand_id),'customer_ids':[str(x) for x in targets],'title':p.title,'body':p.body,'channel':p.channel})
  except Exception: pass
 return {'ok':True,'status':status,'recipients':count}
@router.get('/customer/{code}')
async def inbox(code:str,db:AsyncSession=Depends(get_db)):
 c=await db.scalar(select(Customer).where(Customer.membership_code==code));
 if not c:return []
 rows=(await db.scalars(select(Notification).where(Notification.customer_id==c.id,Notification.status=='sent').order_by(Notification.created_at.desc()))).all(); return [{'id':str(x.id),'title':x.title,'body':x.body,'is_read':x.is_read,'created_at':x.created_at} for x in rows]
