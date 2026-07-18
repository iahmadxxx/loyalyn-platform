import os,secrets,uuid
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException,UploadFile,File,Form
from pydantic import BaseModel,EmailStr,Field
from sqlalchemy import select,func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.api.deps import current_user,allow
from app.models import Brand,Branch,Customer,Employee,MembershipTier,Reward,StampProgram,WalletCertificate,WalletPass,AuditLog,LoyaltyTransaction

router=APIRouter()

def guard_brand(u,brand_id):
    if u.brand_id and str(u.brand_id)!=str(brand_id): raise HTTPException(403,'Brand access denied')

class BranchIn(BaseModel): brand_id:uuid.UUID; name:str; address:str|None=None
class EmployeeIn(BaseModel): brand_id:uuid.UUID; branch_id:uuid.UUID|None=None; name:str; email:EmailStr; phone:str|None=None; role:str='cashier'; permissions:dict={}
class TierIn(BaseModel): brand_id:uuid.UUID; name:str; rank:int=0; color:str='#C6FF4A'; min_points:int=0; min_spend:int=0; points_multiplier:int=1; benefits:dict={}
class RewardIn(BaseModel): brand_id:uuid.UUID; name:str; description:str|None=None; points_cost:int=Field(ge=0); stock:int|None=None; image_url:str|None=None
class StampIn(BaseModel): brand_id:uuid.UUID; name:str; required_stamps:int=Field(ge=1,le=100); reward_title:str; stamp_icon:str='star'
class RedeemIn(BaseModel): reward_id:uuid.UUID; branch_id:uuid.UUID|None=None

@router.get('/branches')
async def branches(brand_id:uuid.UUID,db:AsyncSession=Depends(get_db),u=Depends(current_user)):
 guard_brand(u,brand_id); xs=(await db.scalars(select(Branch).where(Branch.brand_id==brand_id).order_by(Branch.created_at.desc()))).all(); return [dict(id=str(x.id),brand_id=str(x.brand_id),name=x.name,address=x.address,is_active=x.is_active) for x in xs]
@router.post('/branches',status_code=201)
async def branch_add(p:BranchIn,db:AsyncSession=Depends(get_db),u=Depends(allow('owner','admin','manager'))):
 guard_brand(u,p.brand_id); x=Branch(**p.model_dump());db.add(x);await db.flush();db.add(AuditLog(brand_id=p.brand_id,actor_id=u.id,action='branch_created',entity_type='branch',entity_id=str(x.id)));await db.commit();return {'id':str(x.id)}
@router.delete('/branches/{id}')
async def branch_del(id:uuid.UUID,db:AsyncSession=Depends(get_db),u=Depends(allow('owner','admin'))):
 x=await db.get(Branch,id); 
 if not x: raise HTTPException(404,'Branch not found')
 guard_brand(u,x.brand_id); x.is_active=False;await db.commit();return {'ok':True}

@router.get('/employees')
async def employees(brand_id:uuid.UUID,db:AsyncSession=Depends(get_db),u=Depends(current_user)):
 guard_brand(u,brand_id);xs=(await db.scalars(select(Employee).where(Employee.brand_id==brand_id).order_by(Employee.created_at.desc()))).all();return [dict(id=str(x.id),name=x.name,email=x.email,phone=x.phone,role=x.role,branch_id=str(x.branch_id) if x.branch_id else None,permissions=x.permissions,is_active=x.is_active) for x in xs]
@router.post('/employees',status_code=201)
async def employee_add(p:EmployeeIn,db:AsyncSession=Depends(get_db),u=Depends(allow('owner','admin','manager'))):
 guard_brand(u,p.brand_id);x=Employee(**p.model_dump());db.add(x);await db.flush();db.add(AuditLog(brand_id=p.brand_id,actor_id=u.id,action='employee_created',entity_type='employee',entity_id=str(x.id)));await db.commit();return {'id':str(x.id)}
@router.patch('/employees/{id}/toggle')
async def employee_toggle(id:uuid.UUID,db:AsyncSession=Depends(get_db),u=Depends(allow('owner','admin','manager'))):
 x=await db.get(Employee,id)
 if not x: raise HTTPException(404,'Employee not found')
 guard_brand(u,x.brand_id);x.is_active=not x.is_active;await db.commit();return {'ok':True,'is_active':x.is_active}

@router.get('/tiers')
async def tiers(brand_id:uuid.UUID,db:AsyncSession=Depends(get_db),u=Depends(current_user)):
 guard_brand(u,brand_id);xs=(await db.scalars(select(MembershipTier).where(MembershipTier.brand_id==brand_id).order_by(MembershipTier.rank))).all();return [dict(id=str(x.id),name=x.name,rank=x.rank,color=x.color,min_points=x.min_points,min_spend=x.min_spend,points_multiplier=x.points_multiplier,benefits=x.benefits,is_active=x.is_active) for x in xs]
@router.post('/tiers',status_code=201)
async def tier_add(p:TierIn,db:AsyncSession=Depends(get_db),u=Depends(allow('owner','admin','manager'))):
 guard_brand(u,p.brand_id);x=MembershipTier(**p.model_dump());db.add(x);await db.commit();await db.refresh(x);return {'id':str(x.id)}
@router.delete('/tiers/{id}')
async def tier_del(id:uuid.UUID,db:AsyncSession=Depends(get_db),u=Depends(allow('owner','admin'))):
 x=await db.get(MembershipTier,id)
 if not x: raise HTTPException(404,'Tier not found')
 guard_brand(u,x.brand_id);await db.delete(x);await db.commit();return {'ok':True}

@router.get('/rewards')
async def rewards(brand_id:uuid.UUID,db:AsyncSession=Depends(get_db),u=Depends(current_user)):
 guard_brand(u,brand_id);xs=(await db.scalars(select(Reward).where(Reward.brand_id==brand_id).order_by(Reward.created_at.desc()))).all();return [dict(id=str(x.id),name=x.name,description=x.description,points_cost=x.points_cost,stock=x.stock,image_url=x.image_url,is_active=x.is_active) for x in xs]
@router.post('/rewards',status_code=201)
async def reward_add(p:RewardIn,db:AsyncSession=Depends(get_db),u=Depends(allow('owner','admin','manager'))):
 guard_brand(u,p.brand_id);x=Reward(**p.model_dump());db.add(x);await db.commit();await db.refresh(x);return {'id':str(x.id)}
@router.post('/customers/{customer_id}/redeem')
async def redeem(customer_id:uuid.UUID,p:RedeemIn,db:AsyncSession=Depends(get_db),u=Depends(allow('owner','admin','manager','employee'))):
 c=await db.get(Customer,customer_id);r=await db.get(Reward,p.reward_id)
 if not c or not r or c.brand_id!=r.brand_id: raise HTTPException(404,'Customer or reward not found')
 guard_brand(u,c.brand_id)
 if c.points<r.points_cost: raise HTTPException(400,'Insufficient points')
 if r.stock is not None and r.stock<=0: raise HTTPException(400,'Reward out of stock')
 c.points-=r.points_cost
 if r.stock is not None:r.stock-=1
 db.add(LoyaltyTransaction(brand_id=c.brand_id,branch_id=p.branch_id,customer_id=c.id,actor_id=u.id,action='redeem_reward',delta_points=-r.points_cost,metadata_json={'reward_id':str(r.id),'reward_name':r.name}))
 await db.commit();return {'ok':True,'points':c.points}

@router.get('/stamp-programs')
async def stamps(brand_id:uuid.UUID,db:AsyncSession=Depends(get_db),u=Depends(current_user)):
 guard_brand(u,brand_id);xs=(await db.scalars(select(StampProgram).where(StampProgram.brand_id==brand_id).order_by(StampProgram.created_at.desc()))).all();return [dict(id=str(x.id),name=x.name,required_stamps=x.required_stamps,reward_title=x.reward_title,stamp_icon=x.stamp_icon,is_active=x.is_active) for x in xs]
@router.post('/stamp-programs',status_code=201)
async def stamp_add(p:StampIn,db:AsyncSession=Depends(get_db),u=Depends(allow('owner','admin','manager'))):
 guard_brand(u,p.brand_id);x=StampProgram(**p.model_dump());db.add(x);await db.commit();await db.refresh(x);return {'id':str(x.id)}

@router.get('/audit')
async def audit(brand_id:uuid.UUID,db:AsyncSession=Depends(get_db),u=Depends(allow('owner','admin','manager'))):
 guard_brand(u,brand_id);xs=(await db.scalars(select(AuditLog).where(AuditLog.brand_id==brand_id).order_by(AuditLog.created_at.desc()).limit(100))).all();return [dict(id=str(x.id),action=x.action,entity_type=x.entity_type,entity_id=x.entity_id,details=x.details,created_at=x.created_at.isoformat()) for x in xs]

@router.get('/wallet/certificates')
async def certs(brand_id:uuid.UUID,db:AsyncSession=Depends(get_db),u=Depends(allow('owner','admin','manager'))):
 guard_brand(u,brand_id);xs=(await db.scalars(select(WalletCertificate).where(WalletCertificate.brand_id==brand_id).order_by(WalletCertificate.created_at.desc()))).all();return [dict(id=str(x.id),filename=x.filename,certificate_type=x.certificate_type,status=x.status,expires_at=x.expires_at.isoformat() if x.expires_at else None,created_at=x.created_at.isoformat()) for x in xs]
@router.post('/wallet/certificates',status_code=201)
async def cert_upload(brand_id:uuid.UUID=Form(...),certificate_type:str=Form('p12'),file:UploadFile=File(...),db:AsyncSession=Depends(get_db),u=Depends(allow('owner','admin'))):
 guard_brand(u,brand_id)
 if not file.filename or not file.filename.lower().endswith(('.p12','.pem','.cer')): raise HTTPException(400,'Only p12, pem or cer files are accepted')
 d=Path('/app/data/certificates')/str(brand_id);d.mkdir(parents=True,exist_ok=True);name=f'{secrets.token_hex(8)}-{Path(file.filename).name}';path=d/name;path.write_bytes(await file.read())
 x=WalletCertificate(brand_id=brand_id,filename=file.filename,storage_path=str(path),certificate_type=certificate_type);db.add(x);await db.commit();await db.refresh(x);return {'id':str(x.id),'filename':x.filename}

@router.post('/wallet/passes/{customer_id}',status_code=201)
async def issue_pass(customer_id:uuid.UUID,db:AsyncSession=Depends(get_db),u=Depends(allow('owner','admin','manager'))):
 c=await db.get(Customer,customer_id)
 if not c: raise HTTPException(404,'Customer not found')
 guard_brand(u,c.brand_id);x=await db.scalar(select(WalletPass).where(WalletPass.customer_id==c.id))
 if not x:x=WalletPass(brand_id=c.brand_id,customer_id=c.id,serial_number=secrets.token_urlsafe(18),public_token=secrets.token_urlsafe(24));db.add(x);await db.commit();await db.refresh(x)
 return {'id':str(x.id),'serial_number':x.serial_number,'public_token':x.public_token,'card_url':f'/card/{x.public_token}'}

@router.get('/public/card/{token}')
async def public_card(token:str,db:AsyncSession=Depends(get_db)):
 p=await db.scalar(select(WalletPass).where(WalletPass.public_token==token,WalletPass.status=='active'))
 if not p: raise HTTPException(404,'Card not found')
 c=await db.get(Customer,p.customer_id);b=await db.get(Brand,p.brand_id)
 return {'brand':{'name':b.name,'logo_url':b.logo_url,'primary_color':b.primary_color,'accent_color':b.accent_color},'customer':{'name':c.name,'membership_code':c.membership_code,'points':c.points,'stamps':c.stamps,'tier':c.tier,'available_rewards':c.available_rewards},'serial_number':p.serial_number}
