from fastapi import APIRouter,Depends
from sqlalchemy import select,func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models import Brand,Customer,LoyaltyTransaction,Notification
from app.api.deps import current_user
router=APIRouter()
@router.get('')
async def stats(db:AsyncSession=Depends(get_db),u=Depends(current_user)):
 filt=[]
 if u.brand_id: filt=[Brand.id==u.brand_id]
 brands=await db.scalar(select(func.count()).select_from(Brand).where(*filt))
 cf=[] if not u.brand_id else [Customer.brand_id==u.brand_id]
 tf=[] if not u.brand_id else [LoyaltyTransaction.brand_id==u.brand_id]
 nf=[] if not u.brand_id else [Notification.brand_id==u.brand_id]
 customers=await db.scalar(select(func.count()).select_from(Customer).where(*cf))
 txs=await db.scalar(select(func.count()).select_from(LoyaltyTransaction).where(*tf))
 notes=await db.scalar(select(func.count()).select_from(Notification).where(*nf))
 recent=(await db.scalars(select(LoyaltyTransaction).where(*tf).order_by(LoyaltyTransaction.created_at.desc()).limit(8))).all()
 return {'brands':brands,'customers':customers,'transactions':txs,'notifications':notes,'recent':[{'id':str(x.id),'action':x.action,'points':x.delta_points,'stamps':x.delta_stamps,'created_at':x.created_at} for x in recent]}
