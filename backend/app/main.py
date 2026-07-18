from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from app.api.routes import auth, brands, customers, dashboard, health, management, notifications, public, stamps, wallet
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models import User

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == settings.bootstrap_admin_email.lower()))
        if not user:
            db.add(User(email=settings.bootstrap_admin_email.lower(), full_name="Loyalyn Platform Owner", password_hash=hash_password(settings.bootstrap_admin_password), role="platform_owner"))
            await db.commit()
        elif user.role in {"owner", "admin"}:
            user.role = "platform_owner"; await db.commit()
    yield

app = FastAPI(title="Loyalyn API", version=settings.app_version, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def browser_security(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.cookies.get("loyalyn_access") and not request.headers.get("authorization"):
        if request.url.path != "/api/auth/login":
            csrf_cookie = request.cookies.get("loyalyn_csrf")
            csrf_header = request.headers.get("x-loyalyn-csrf")
            origin = request.headers.get("origin")
            if origin and origin not in settings.cors_origin_list:
                return JSONResponse({"detail": "مصدر الطلب غير مسموح"}, status_code=403)
            if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
                return JSONResponse({"detail": "تعذر التحقق من أمان الجلسة. حدّث الصفحة وحاول مرة أخرى"}, status_code=403)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(self), geolocation=(), microphone=()")
    if settings.environment.lower() == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

app.include_router(health.router, prefix="/api", tags=["system"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(brands.router, prefix="/api/brands", tags=["brands"])
app.include_router(management.router, prefix="/api/management", tags=["management"])
app.include_router(customers.router, prefix="/api/customers", tags=["customers"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(wallet.router, prefix="/api/wallet", tags=["wallet"])
app.include_router(stamps.router, prefix="/api/stamps", tags=["stamps"])
app.include_router(public.router, prefix="/api/public", tags=["public"])
