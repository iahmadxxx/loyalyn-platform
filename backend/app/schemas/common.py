from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class BrandCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    primary_color: str = Field(default="#111827", pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_color: str = Field(default="#C6FF4A", pattern=r"^#[0-9A-Fa-f]{6}$")

class CustomerCreate(BaseModel):
    brand_id: UUID
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=7, max_length=32)

class StampAction(BaseModel):
    branch_id: UUID | None = None
    idempotency_key: str = Field(min_length=8, max_length=100)

class WalletDesignUpdate(BaseModel):
    design: dict

class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
