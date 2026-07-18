from datetime import datetime,timedelta,timezone
from passlib.context import CryptContext
from jose import jwt,JWTError
from app.core.config import get_settings
pwd=CryptContext(schemes=["bcrypt"],deprecated="auto")
def hash_password(v): return pwd.hash(v)
def verify_password(v,h): return pwd.verify(v,h)
def create_token(user_id,role):
 s=get_settings(); exp=datetime.now(timezone.utc)+timedelta(minutes=s.jwt_expire_minutes)
 return jwt.encode({"sub":str(user_id),"role":role,"exp":exp},s.jwt_secret,algorithm="HS256")
def decode_token(token):
 try:return jwt.decode(token,get_settings().jwt_secret,algorithms=["HS256"])
 except JWTError:return None
