from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models import Brand,Branch,LoyaltyProgram,WalletConfig,AuditLog
from app.schemas.common import BrandCreate,BranchCreate,ProgramUpdate,WalletUpdate
from app.api.deps import current_user,allow
router=APIRouter()
@router.get('')
async def list_all(db:AsyncSession=Depends(get_db),u=Depends(current_user)):
 q=select(Brand).order_by(Brand.created_at.desc())
 if u.brand_id:q=q.where(Brand.id==u.brand_id)
 rows=(await db.scalars(q)).all(); return [{'id':str(x.id),'name':x.name,'slug':x.slug,'is_active':x.is_active,'primary_color':x.primary_color,'accent_color':x.accent_color} for x in rows]
@router.post('',status_code=201)
async def create(p:BrandCreate,db:AsyncSession=Depends(get_db),u=Depends(allow('owner','admin'))):
 if await db.scalar(select(Brand).where(Brand.slug==p.slug)): raise HTTPException(409,'Brand slug already exists')
 b=Brand(**p.model_dump()); db.add(b); await db.flush(); db.add_all([LoyaltyProgram(brand_id=b.id),WalletConfig(brand_id=b.id,design={'showProgress':True}),AuditLog(brand_id=b.id,actor_id=u.id,action='brand_created',entity_type='brand',entity_id=str(b.id))]); await db.commit(); return {'id':str(b.id)}
@router.post('/branches',status_code=201)
async def branch(p:BranchCreate,db:AsyncSession=Depends(get_db),u=Depends(allow('owner','admin','manager'))):
 x=Branch(**p.model_dump()); db.add(x); await db.commit(); await db.refresh(x); return {'id':str(x.id),'name':x.name}
@router.get('/{brand_id}/program')
async def get_program(brand_id:str,db:AsyncSession=Depends(get_db),u=Depends(current_user)):
 x=await db.scalar(select(LoyaltyProgram).where(LoyaltyProgram.brand_id==brand_id)); return {'required_stamps':x.required_stamps,'points_per_visit':x.points_per_visit,'reward_points':x.reward_points,'reward_title':x.reward_title}
@router.put('/{brand_id}/program')
async def program(brand_id:str,p:ProgramUpdate,db:AsyncSession=Depends(get_db),u=Depends(allow('owner','admin','manager'))):
 x=await db.scalar(select(LoyaltyProgram).where(LoyaltyProgram.brand_id==brand_id));
 if not x: raise HTTPException(404,'Program not found')
 for k,v in p.model_dump().items(): setattr(x,k,v)
 await db.commit(); return {'ok':True}
@router.get('/{brand_id}/wallet')
async def wallet_get(brand_id:str,db:AsyncSession=Depends(get_db),u=Depends(current_user)):
 x=await db.scalar(select(WalletConfig).where(WalletConfig.brand_id==brand_id)); return {'enabled':x.enabled,'status':x.validation_status,'pass_type_identifier':x.pass_type_identifier,'team_identifier':x.team_identifier,'organization_name':x.organization_name,'design':x.design}
@router.put('/{brand_id}/wallet')
async def wallet_put(brand_id:str,p:WalletUpdate,db:AsyncSession=Depends(get_db),u=Depends(allow('owner','admin'))):
 x=await db.scalar(select(WalletConfig).where(WalletConfig.brand_id==brand_id));
 for k,v in p.model_dump().items(): setattr(x,k,v)
 x.validation_status='pending_certificate' if not x.pass_type_identifier else 'configuration_saved'; await db.commit(); return {'ok':True,'status':x.validation_status}
