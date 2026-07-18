import uuid
from datetime import datetime, timezone
from fastapi import Cookie, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import decode_token
from app.db.session import get_db
from app.models import AuthSession, User, UserBrandAccess

bearer = HTTPBearer(auto_error=False)
PLATFORM_ROLES = {"platform_owner"}
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "brand_admin": {"*"},
    "manager": {
        "brand.view", "branches.view", "branches.manage", "customers.view", "customers.list", "customers.manage", "customers.create", "customers.edit", "customers.history",
        "loyalty.view", "loyalty.manage", "loyalty.apply", "loyalty.manual", "loyalty.reverse", "rewards.redeem", "staff.view",
        "wallet.view", "wallet.design", "wallet.issue", "campaigns.view", "campaigns.manage", "audit.view", "fast_scan.use",
    },
    "employee": {
        "brand.view", "branches.scoped", "customers.view", "customers.create", "loyalty.view",
        "loyalty.apply", "rewards.redeem", "wallet.issue", "fast_scan.use",
    },
}

async def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    loyalyn_access: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    raw_token = creds.credentials if creds else loyalyn_access
    if not raw_token:
        raise HTTPException(401, "Authentication required")
    payload = decode_token(raw_token)
    if not payload:
        raise HTTPException(401, "Invalid or expired token")
    try:
        uid = uuid.UUID(payload["sub"])
        sid = uuid.UUID(payload["sid"])
    except (KeyError, ValueError):
        raise HTTPException(401, "Invalid token")
    session = await db.scalar(select(AuthSession).where(
        AuthSession.id == sid, AuthSession.user_id == uid, AuthSession.revoked_at.is_(None)
    ))
    if not session:
        raise HTTPException(401, "Session revoked")
    expires = session.expires_at if session.expires_at.tzinfo else session.expires_at.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        raise HTTPException(401, "Session expired")
    user = await db.scalar(select(User).where(User.id == uid, User.is_active.is_(True)))
    if not user:
        raise HTTPException(401, "User unavailable")
    return user

def allow(*roles):
    normalized = set(roles)
    async def guard(user=Depends(current_user)):
        role = "platform_owner" if user.role in PLATFORM_ROLES else user.role
        if role not in normalized and user.role not in normalized:
            raise HTTPException(403, "Insufficient permissions")
        return user
    return guard

def effective_permissions(role: str, custom: dict | None = None) -> dict[str, bool]:
    custom = custom or {}
    result = {key: True for key in ROLE_PERMISSIONS.get(role, set())}
    for key, value in custom.items():
        if isinstance(value, bool):
            result[key] = value
    # Backward compatibility for V3/V4 custom permission payloads.
    if result.get("customers.manage", False):
        if "customers.create" not in custom:
            result["customers.create"] = True
        if "customers.edit" not in custom:
            result["customers.edit"] = True
    if result.get("loyalty.manage", False) and "loyalty.manual" not in custom:
        result["loyalty.manual"] = True
    return result

async def brand_access(db: AsyncSession, user: User, brand_id: uuid.UUID, *, permission: str | None = None, write: bool = False) -> UserBrandAccess | None:
    if user.role in PLATFORM_ROLES:
        return None
    access = await db.scalar(select(UserBrandAccess).where(
        UserBrandAccess.user_id == user.id,
        UserBrandAccess.brand_id == brand_id,
        UserBrandAccess.is_active.is_(True),
    ))
    role = access.role if access else user.role
    custom = access.permissions if access else {}
    if not access and not (user.brand_id and user.brand_id == brand_id):
        raise HTTPException(403, "Brand access denied")
    permissions = effective_permissions(role, custom)
    required = permission or ("write" if write else None)
    if required and not permissions.get("*", False) and not permissions.get(required, False):
        raise HTTPException(403, "Permission denied")
    return access

def operational_branch(access: UserBrandAccess | None, requested: uuid.UUID | None) -> uuid.UUID | None:
    """Force branch-scoped employees to their assigned branch."""
    if access and access.role == "employee" and access.branch_id:
        if requested and requested != access.branch_id:
            raise HTTPException(403, "هذا الحساب مرتبط بفرع آخر")
        return access.branch_id
    return requested


async def require_platform_owner(user=Depends(current_user)):
    if user.role not in PLATFORM_ROLES:
        raise HTTPException(403, "Platform owner access required")
    return user
