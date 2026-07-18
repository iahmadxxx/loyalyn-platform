from datetime import datetime
from uuid import UUID
from pydantic import BaseModel,EmailStr,Field
class Login(BaseModel): email:EmailStr; password:str
class BrandCreate(BaseModel): name:str=Field(min_length=2,max_length=120); slug:str=Field(pattern=r"^[a-z0-9-]+$"); primary_color:str="#111827"; accent_color:str="#C6FF4A"
class BranchCreate(BaseModel): brand_id:UUID; name:str; address:str|None=None
class CustomerCreate(BaseModel): brand_id:UUID; name:str; phone:str; email:EmailStr|None=None
class LoyaltyAction(BaseModel): branch_id:UUID|None=None; points:int=0; stamps:int=0; note:str|None=None; idempotency_key:str
class NotificationCreate(BaseModel): brand_id:UUID; customer_id:UUID|None=None; title:str; body:str; channel:str="in_app"; audience:str="individual"; scheduled_at:datetime|None=None
class ProgramUpdate(BaseModel): required_stamps:int=Field(ge=1,le=100); points_per_visit:int=Field(ge=0,le=10000); reward_points:int=Field(ge=1,le=100000); reward_title:str
class WalletUpdate(BaseModel): pass_type_identifier:str|None=None; team_identifier:str|None=None; organization_name:str|None=None; design:dict={}
