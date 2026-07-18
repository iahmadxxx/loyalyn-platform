import uuid
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import decode_token
from app.db.session import get_db
from app.models import User, UserBrandAccess

bearer = HTTPBearer(auto_error=False)
PLATFORM_ROLES = {"platform_owner"}
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "brand_admin": {"*"},
    "manager": {
        "brand.view", "branches.view", "branches.manage", "customers.view", "customers.manage",
        "loyalty.view", "loyalty.manage", "loyalty.apply", "rewards.redeem", "staff.view",
        "wallet.view", "wallet.design", "wallet.issue", "campaigns.view", "campaigns.manage", "audit.view",
    },
    "employee": {"brand.view", "customers.view", "customers.manage", "loyalty.view", "loyalty.apply", "rewards.redeem", "wallet.issue"},
}


async def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    if not creds:
        raise HTTPException(401, "Authentication required")
    payload = decode_token(creds.credentials)
    if not payload:
        raise HTTPException(401, "Invalid or expired token")
    try:
        uid = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(401, "Invalid token")
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
    defaults = ROLE_PERMISSIONS.get(role, set())
    result = {key: True for key in defaults}
    for key, value in (custom or {}).items():
        if isinstance(value, bool):
            result[key] = value
    return result


async def brand_access(
    db: AsyncSession,
    user: User,
    brand_id: uuid.UUID,
    *,
    permission: str | None = None,
    write: bool = False,
) -> UserBrandAccess | None:
    if user.role in PLATFORM_ROLES:
        return None
    access = await db.scalar(
        select(UserBrandAccess).where(
            UserBrandAccess.user_id == user.id,
            UserBrandAccess.brand_id == brand_id,
            UserBrandAccess.is_active.is_(True),
        )
    )
    role = access.role if access else user.role
    custom = access.permissions if access else {}
    if not access and not (user.brand_id and user.brand_id == brand_id):
        raise HTTPException(403, "Brand access denied")
    permissions = effective_permissions(role, custom)
    required = permission or ("write" if write else None)
    if required and "*" not in permissions and not permissions.get(required, False):
        raise HTTPException(403, "Permission denied")
    return access


async def require_platform_owner(user=Depends(current_user)):
    if user.role not in PLATFORM_ROLES:
        raise HTTPException(403, "Platform owner access required")
    return user
