import secrets
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models import Customer,LoyaltyProgram,LoyaltyTransaction,AuditLog
from app.schemas.common import CustomerCreate,LoyaltyAction
from app.api.deps import current_user,allow
router=APIRouter()
def out(c): return {'id':str(c.id),'brand_id':str(c.brand_id),'name':c.name,'phone':c.phone,'email':c.email,'membership_code':c.membership_code,'points':c.points,'stamps':c.stamps,'available_rewards':c.available_rewards,'tier':c.tier,'visits':c.visits,'is_active':c.is_active,'created_at':c.created_at}
@router.get('')
async def list_all(brand_id:str|None=None,q:str|None=None,db:AsyncSession=Depends(get_db),u=Depends(current_user)):
 s=select(Customer).order_by(Customer.created_at.desc()).limit(500)
 if u.brand_id:s=s.where(Customer.brand_id==u.brand_id)
 elif brand_id:s=s.where(Customer.brand_id==brand_id)
 if q:s=s.where((Customer.name.ilike(f'%{q}%'))|(Customer.phone.ilike(f'%{q}%')))
 return [out(x) for x in (await db.scalars(s)).all()]
@router.post('',status_code=201)
async def create(p:CustomerCreate,db:AsyncSession=Depends(get_db),u=Depends(allow('owner','admin','manager','employee'))):
 x=await db.scalar(select(Customer).where(Customer.brand_id==p.brand_id,Customer.phone==p.phone))
 if x:return {**out(x),'existing':True}
 x=Customer(**p.model_dump(),membership_code=secrets.token_urlsafe(18)); db.add(x); await db.flush(); db.add(AuditLog(brand_id=x.brand_id,actor_id=u.id,action='customer_created',entity_type='customer',entity_id=str(x.id))); await db.commit(); await db.refresh(x); return {**out(x),'existing':False}
@router.get('/code/{code}')
async def by_code(code:str,db:AsyncSession=Depends(get_db),u=Depends(current_user)):
 x=await db.scalar(select(Customer).where(Customer.membership_code==code));
 if not x: raise HTTPException(404,'Customer not found')
 return out(x)
@router.post('/{customer_id}/loyalty')
async def loyalty(customer_id:str,p:LoyaltyAction,db:AsyncSession=Depends(get_db),u=Depends(allow('owner','admin','manager','employee'))):
 old=await db.scalar(select(LoyaltyTransaction).where(LoyaltyTransaction.idempotency_key==p.idempotency_key))
 x=await db.scalar(select(Customer).where(Customer.id==customer_id))
 if not x: raise HTTPException(404,'Customer not found')
 if old:return {**out(x),'duplicate':True}
 program=await db.scalar(select(LoyaltyProgram).where(LoyaltyProgram.brand_id==x.brand_id))
 x.points=max(0,x.points+p.points); x.stamps=max(0,x.stamps+p.stamps); x.visits+=1
 required=program.required_stamps if program else 6; reward_points=program.reward_points if program else 100
 while x.stamps>=required: x.stamps-=required; x.available_rewards+=1
 while x.points>=reward_points: x.points-=reward_points; x.available_rewards+=1
 x.tier='gold' if x.visits>=25 else ('silver' if x.visits>=10 else 'bronze')
 tx=LoyaltyTransaction(brand_id=x.brand_id,branch_id=p.branch_id,customer_id=x.id,actor_id=u.id,action='loyalty_adjusted',delta_points=p.points,delta_stamps=p.stamps,idempotency_key=p.idempotency_key,metadata_json={'note':p.note or ''}); db.add(tx); await db.commit(); await db.refresh(x); return {**out(x),'duplicate':False}
@router.post('/{customer_id}/redeem')
async def redeem(customer_id:str,db:AsyncSession=Depends(get_db),u=Depends(allow('owner','admin','manager','employee'))):
 x=await db.scalar(select(Customer).where(Customer.id==customer_id))
 if not x or x.available_rewards<1: raise HTTPException(400,'No reward available')
 x.available_rewards-=1; db.add(LoyaltyTransaction(brand_id=x.brand_id,customer_id=x.id,actor_id=u.id,action='reward_redeemed')); await db.commit(); return out(x)
