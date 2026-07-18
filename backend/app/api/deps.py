import uuid
from fastapi import Depends,HTTPException
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.core.security import decode_token
from app.models import User
bearer=HTTPBearer(auto_error=False)
async def current_user(creds:HTTPAuthorizationCredentials|None=Depends(bearer),db:AsyncSession=Depends(get_db)):
 if not creds: raise HTTPException(401,"Authentication required")
 payload=decode_token(creds.credentials)
 if not payload: raise HTTPException(401,"Invalid or expired token")
 try: uid=uuid.UUID(payload["sub"])
 except: raise HTTPException(401,"Invalid token")
 user=await db.scalar(select(User).where(User.id==uid,User.is_active==True))
 if not user: raise HTTPException(401,"User unavailable")
 return user
def allow(*roles):
 async def guard(user=Depends(current_user)):
  if user.role not in roles: raise HTTPException(403,"Insufficient permissions")
  return user
 return guard
