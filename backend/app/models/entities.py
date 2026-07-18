import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDTimestampMixin

class Brand(UUIDTimestampMixin, Base):
    __tablename__ = "brands"
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    logo_url: Mapped[str | None] = mapped_column(Text)
    primary_color: Mapped[str] = mapped_column(String(7), default="#111827")
    accent_color: Mapped[str] = mapped_column(String(7), default="#C6FF4A")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    branches = relationship("Branch", back_populates="brand", cascade="all, delete-orphan")

class Branch(UUIDTimestampMixin, Base):
    __tablename__ = "branches"
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    brand = relationship("Brand", back_populates="branches")

class Customer(UUIDTimestampMixin, Base):
    __tablename__ = "customers"
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    membership_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    stamps: Mapped[int] = mapped_column(Integer, default=0)
    available_rewards: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("brand_id", "phone", name="uq_customer_brand_phone"),)

class LoyaltyProgram(UUIDTimestampMixin, Base):
    __tablename__ = "loyalty_programs"
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), unique=True)
    program_type: Mapped[str] = mapped_column(String(30), default="stamps")
    required_stamps: Mapped[int] = mapped_column(Integer, default=6)
    reward_title: Mapped[str] = mapped_column(String(160), default="Free reward")
    reset_after_redeem: Mapped[bool] = mapped_column(Boolean, default=True)
    rules: Mapped[dict] = mapped_column(JSON, default=dict)

class LoyaltyTransaction(UUIDTimestampMixin, Base):
    __tablename__ = "loyalty_transactions"
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    delta_stamps: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

class WalletConfig(UUIDTimestampMixin, Base):
    __tablename__ = "wallet_configs"
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), unique=True)
    provider: Mapped[str] = mapped_column(String(30), default="apple_direct")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    pass_type_identifier: Mapped[str | None] = mapped_column(String(180))
    team_identifier: Mapped[str | None] = mapped_column(String(32))
    organization_name: Mapped[str | None] = mapped_column(String(160))
    encrypted_certificate: Mapped[str | None] = mapped_column(Text)
    encrypted_password: Mapped[str | None] = mapped_column(Text)
    certificate_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validation_status: Mapped[str] = mapped_column(String(30), default="not_configured")
    last_validation_error: Mapped[str | None] = mapped_column(Text)

class WalletDesign(UUIDTimestampMixin, Base):
    __tablename__ = "wallet_designs"
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    design: Mapped[dict] = mapped_column(JSON, default=dict)

class AuditLog(UUIDTimestampMixin, Base):
    __tablename__ = "audit_logs"
    brand_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("brands.id", ondelete="SET NULL"), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(80))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64))
