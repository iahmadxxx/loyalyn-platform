from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from app.core.config import get_settings
from app.core.security import hash_password
from app.models import Base,User
from app.db.session import engine,AsyncSessionLocal
from app.api.routes import health,auth,dashboard,brands,customers,notifications,management
settings=get_settings()
@asynccontextmanager
async def lifespan(app:FastAPI):
 async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
 async with AsyncSessionLocal() as db:
  if not await db.scalar(select(User).where(User.email==settings.bootstrap_admin_email.lower())):
   db.add(User(email=settings.bootstrap_admin_email.lower(),full_name='Loyalyn Owner',password_hash=hash_password(settings.bootstrap_admin_password),role='owner')); await db.commit()
 yield
app=FastAPI(title='Loyalyn API',version='2.0.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origin_list,allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
app.include_router(health.router,prefix='/api',tags=['system'])
app.include_router(auth.router,prefix='/api/auth',tags=['auth'])
app.include_router(dashboard.router,prefix='/api/dashboard',tags=['dashboard'])
app.include_router(brands.router,prefix='/api/brands',tags=['brands'])
app.include_router(customers.router,prefix='/api/customers',tags=['customers'])
app.include_router(notifications.router,prefix='/api/notifications',tags=['notifications'])

app.include_router(management.router,prefix='/api/manage',tags=['management'])
