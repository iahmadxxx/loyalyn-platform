from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import PLATFORM_ROLES, current_user, effective_permissions
from app.core.config import get_settings
from app.core.security import create_token, new_csrf_token, new_refresh_token, token_hash, verify_password
from app.db.session import get_db
from app.models import AuthSession, Brand, User, UserBrandAccess
from app.schemas.common import Login

router = APIRouter()
settings = get_settings()

def _secure_cookie() -> bool:
    return settings.environment.lower() not in {"development", "test", "local"}

def _csrf_cookie_domain() -> str | None:
    if not _secure_cookie():
        return None
    value = settings.cookie_domain.strip()
    return value or None

def _set_session_cookies(response: Response, access_token: str, refresh_token: str, csrf_token: str) -> None:
    secure = _secure_cookie()
    response.set_cookie("loyalyn_access", access_token, httponly=True, secure=secure, samesite="lax", max_age=settings.jwt_expire_minutes * 60, path="/")
    response.set_cookie("loyalyn_refresh", refresh_token, httponly=True, secure=secure, samesite="lax", max_age=settings.refresh_expire_days * 86400, path="/api/auth")
    response.set_cookie("loyalyn_csrf", csrf_token, httponly=False, secure=secure, samesite="lax", max_age=settings.refresh_expire_days * 86400, path="/", domain=_csrf_cookie_domain())

def _clear_session_cookies(response: Response) -> None:
    secure = _secure_cookie()
    for name, path, httponly in (("loyalyn_access", "/", True), ("loyalyn_refresh", "/api/auth", True), ("loyalyn_csrf", "/", False)):
        response.delete_cookie(name, path=path, secure=secure, httponly=httponly, samesite="lax", domain=_csrf_cookie_domain() if name == "loyalyn_csrf" else None)

def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

def _check_csrf(request: Request, csrf_cookie: str | None) -> None:
    csrf_header = request.headers.get("x-loyalyn-csrf")
    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        raise HTTPException(403, "تعذر التحقق من أمان الجلسة. حدّث الصفحة وحاول مرة أخرى")

@router.post("/login")
async def login(payload: Login, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "البريد الإلكتروني أو كلمة المرور غير صحيحة")
    now = datetime.now(timezone.utc)
    user.last_login_at = now
    refresh_token = new_refresh_token()
    session = AuthSession(user_id=user.id, refresh_token_hash=token_hash(refresh_token), expires_at=now + timedelta(days=settings.refresh_expire_days), user_agent=(request.headers.get("user-agent") or "")[:255] or None, ip_address=request.client.host if request.client else None)
    db.add(session)
    await db.flush()
    await db.commit()
    role = "platform_owner" if user.role in PLATFORM_ROLES else user.role
    access_token, csrf = create_token(user.id, role, session.id), new_csrf_token()
    _set_session_cookies(response, access_token, refresh_token, csrf)
    return {"ok": True, "access_token": access_token, "token_type": "bearer", "expires_in": settings.jwt_expire_minutes * 60, "user": {"id": str(user.id), "name": user.full_name, "email": user.email, "role": role}}

@router.post("/refresh")
async def refresh(request: Request, response: Response, loyalyn_refresh: str | None = Cookie(default=None), loyalyn_csrf: str | None = Cookie(default=None), db: AsyncSession = Depends(get_db)):
    _check_csrf(request, loyalyn_csrf)
    if not loyalyn_refresh:
        raise HTTPException(401, "انتهت الجلسة")
    now = datetime.now(timezone.utc)
    session = await db.scalar(select(AuthSession).where(AuthSession.refresh_token_hash == token_hash(loyalyn_refresh)))
    if not session or session.revoked_at or _aware(session.expires_at) <= now:
        raise HTTPException(401, "انتهت الجلسة")
    user = await db.get(User, session.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "الحساب غير متاح")
    session.revoked_at = now; session.last_used_at = now
    next_refresh = new_refresh_token()
    next_session = AuthSession(user_id=user.id, refresh_token_hash=token_hash(next_refresh), expires_at=now + timedelta(days=settings.refresh_expire_days), user_agent=(request.headers.get("user-agent") or "")[:255] or None, ip_address=request.client.host if request.client else None)
    db.add(next_session)
    await db.flush()
    await db.commit()
    role = "platform_owner" if user.role in PLATFORM_ROLES else user.role
    csrf = new_csrf_token(); _set_session_cookies(response, create_token(user.id, role, next_session.id), next_refresh, csrf)
    return {"ok": True, "expires_in": settings.jwt_expire_minutes * 60}

@router.post("/logout")
async def logout(request: Request, response: Response, loyalyn_refresh: str | None = Cookie(default=None), loyalyn_csrf: str | None = Cookie(default=None), db: AsyncSession = Depends(get_db)):
    if loyalyn_refresh:
        _check_csrf(request, loyalyn_csrf)
        await db.execute(update(AuthSession).where(AuthSession.refresh_token_hash == token_hash(loyalyn_refresh), AuthSession.revoked_at.is_(None)).values(revoked_at=datetime.now(timezone.utc)))
        await db.commit()
    _clear_session_cookies(response)
    return {"ok": True}

@router.get("/me")
async def me(user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    role = "platform_owner" if user.role in PLATFORM_ROLES else user.role
    if role == "platform_owner":
        brands = list((await db.scalars(select(Brand).order_by(Brand.name))).all())
        access = [{"id": str(b.id), "name": b.name, "slug": b.slug, "role": "platform_owner", "branch_id": None, "permissions": {"*": True}} for b in brands]
    else:
        rows = (await db.execute(select(UserBrandAccess, Brand).join(Brand, Brand.id == UserBrandAccess.brand_id).where(UserBrandAccess.user_id == user.id, UserBrandAccess.is_active.is_(True), Brand.is_active.is_(True)).order_by(Brand.name))).all()
        access = [{"id": str(b.id), "name": b.name, "slug": b.slug, "role": a.role, "branch_id": str(a.branch_id) if a.branch_id else None, "permissions": effective_permissions(a.role, a.permissions or {})} for a, b in rows]
        if not access and user.brand_id:
            brand = await db.get(Brand, user.brand_id)
            if brand:
                access = [{"id": str(brand.id), "name": brand.name, "slug": brand.slug, "role": role, "branch_id": None, "permissions": effective_permissions(role, {})}]
    return {"id": str(user.id), "name": user.full_name, "email": user.email, "role": role, "brand_id": str(user.brand_id) if user.brand_id else None, "brands": access}
