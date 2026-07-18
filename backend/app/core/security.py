import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import get_settings

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(value: str) -> str:
    return pwd.hash(value)

def verify_password(value: str, hashed: str) -> bool:
    try:
        return pwd.verify(value, hashed)
    except Exception:
        return False

def create_token(user_id, role: str, session_id=None) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "role": role, "iat": now, "exp": exp, "type": "access"}
    if session_id is not None:
        payload["sid"] = str(session_id)
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

def decode_token(token: str):
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
        return payload if payload.get("type", "access") == "access" else None
    except JWTError:
        return None

def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)

def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)

def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def _fernet() -> Fernet:
    settings = get_settings()
    raw = settings.encryption_key or settings.jwt_secret
    key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode("utf-8")).digest())
    return Fernet(key)

def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")

def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise RuntimeError("Unable to decrypt protected secret") from exc
