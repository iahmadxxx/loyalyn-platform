from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.models import Base
from app.db.session import engine
from app.api.routes import health, brands, customers, wallet

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="Loyalyn API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(health.router, prefix="/api", tags=["system"])
app.include_router(brands.router, prefix="/api/brands", tags=["brands"])
app.include_router(customers.router, prefix="/api/customers", tags=["customers"])
app.include_router(wallet.router, prefix="/api/wallet", tags=["wallet"])
