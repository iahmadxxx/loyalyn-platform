from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models import User
from app.schemas.common import Login
from app.core.security import verify_password,create_token
from app.api.deps import current_user
router=APIRouter()
@router.post('/login')
async def login(p:Login,db:AsyncSession=Depends(get_db)):
 u=await db.scalar(select(User).where(User.email==p.email.lower()))
 if not u or not verify_password(p.password,u.password_hash): raise HTTPException(401,'Invalid email or password')
 return {'access_token':create_token(u.id,u.role),'token_type':'bearer','user':{'id':str(u.id),'name':u.full_name,'email':u.email,'role':u.role}}
@router.get('/me')
async def me(u=Depends(current_user)): return {'id':str(u.id),'name':u.full_name,'email':u.email,'role':u.role,'brand_id':str(u.brand_id) if u.brand_id else None}
