import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDTimestampMixin

class User(UUIDTimestampMixin, Base):
    __tablename__="users"
    email: Mapped[str]=mapped_column(String(190),unique=True,index=True)
    full_name: Mapped[str]=mapped_column(String(120))
    password_hash: Mapped[str]=mapped_column(String(255))
    role: Mapped[str]=mapped_column(String(30),default="owner")
    brand_id: Mapped[uuid.UUID|None]=mapped_column(ForeignKey("brands.id",ondelete="SET NULL"),nullable=True,index=True)
    is_active: Mapped[bool]=mapped_column(Boolean,default=True)

class Brand(UUIDTimestampMixin, Base):
    __tablename__="brands"
    name: Mapped[str]=mapped_column(String(120))
    slug: Mapped[str]=mapped_column(String(80),unique=True,index=True)
    logo_url: Mapped[str|None]=mapped_column(Text,nullable=True)
    primary_color: Mapped[str]=mapped_column(String(7),default="#111827")
    accent_color: Mapped[str]=mapped_column(String(7),default="#C6FF4A")
    is_active: Mapped[bool]=mapped_column(Boolean,default=True)
    branches=relationship("Branch",cascade="all, delete-orphan")

class Branch(UUIDTimestampMixin, Base):
    __tablename__="branches"
    brand_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("brands.id",ondelete="CASCADE"),index=True)
    name: Mapped[str]=mapped_column(String(120))
    address: Mapped[str|None]=mapped_column(Text,nullable=True)
    is_active: Mapped[bool]=mapped_column(Boolean,default=True)

class Customer(UUIDTimestampMixin, Base):
    __tablename__="customers"
    brand_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("brands.id",ondelete="CASCADE"),index=True)
    name: Mapped[str]=mapped_column(String(120))
    phone: Mapped[str]=mapped_column(String(32))
    email: Mapped[str|None]=mapped_column(String(190),nullable=True)
    membership_code: Mapped[str]=mapped_column(String(64),unique=True,index=True)
    points: Mapped[int]=mapped_column(Integer,default=0)
    stamps: Mapped[int]=mapped_column(Integer,default=0)
    available_rewards: Mapped[int]=mapped_column(Integer,default=0)
    tier: Mapped[str]=mapped_column(String(30),default="bronze")
    visits: Mapped[int]=mapped_column(Integer,default=0)
    is_active: Mapped[bool]=mapped_column(Boolean,default=True)
    __table_args__=(UniqueConstraint("brand_id","phone",name="uq_customer_brand_phone"),)

class LoyaltyProgram(UUIDTimestampMixin, Base):
    __tablename__="loyalty_programs"
    brand_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("brands.id",ondelete="CASCADE"),unique=True)
    program_type: Mapped[str]=mapped_column(String(30),default="hybrid")
    required_stamps: Mapped[int]=mapped_column(Integer,default=6)
    points_per_visit: Mapped[int]=mapped_column(Integer,default=10)
    reward_points: Mapped[int]=mapped_column(Integer,default=100)
    reward_title: Mapped[str]=mapped_column(String(160),default="مكافأة مجانية")
    rules: Mapped[dict]=mapped_column(JSON,default=dict)

class LoyaltyTransaction(UUIDTimestampMixin, Base):
    __tablename__="loyalty_transactions"
    brand_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("brands.id",ondelete="CASCADE"),index=True)
    branch_id: Mapped[uuid.UUID|None]=mapped_column(ForeignKey("branches.id",ondelete="SET NULL"),nullable=True,index=True)
    customer_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("customers.id",ondelete="RESTRICT"),index=True)
    actor_id: Mapped[uuid.UUID|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),nullable=True)
    action: Mapped[str]=mapped_column(String(40))
    delta_points: Mapped[int]=mapped_column(Integer,default=0)
    delta_stamps: Mapped[int]=mapped_column(Integer,default=0)
    idempotency_key: Mapped[str|None]=mapped_column(String(100),unique=True,nullable=True)
    metadata_json: Mapped[dict]=mapped_column("metadata",JSON,default=dict)

class Notification(UUIDTimestampMixin, Base):
    __tablename__="notifications"
    brand_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("brands.id",ondelete="CASCADE"),index=True)
    customer_id: Mapped[uuid.UUID|None]=mapped_column(ForeignKey("customers.id",ondelete="CASCADE"),nullable=True,index=True)
    title: Mapped[str]=mapped_column(String(160))
    body: Mapped[str]=mapped_column(Text)
    channel: Mapped[str]=mapped_column(String(30),default="in_app")
    audience: Mapped[str]=mapped_column(String(30),default="individual")
    status: Mapped[str]=mapped_column(String(30),default="sent")
    scheduled_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    sent_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    is_read: Mapped[bool]=mapped_column(Boolean,default=False)

class WalletConfig(UUIDTimestampMixin, Base):
    __tablename__="wallet_configs"
    brand_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("brands.id",ondelete="CASCADE"),unique=True)
    enabled: Mapped[bool]=mapped_column(Boolean,default=False)
    pass_type_identifier: Mapped[str|None]=mapped_column(String(180),nullable=True)
    team_identifier: Mapped[str|None]=mapped_column(String(32),nullable=True)
    organization_name: Mapped[str|None]=mapped_column(String(160),nullable=True)
    validation_status: Mapped[str]=mapped_column(String(30),default="not_configured")
    design: Mapped[dict]=mapped_column(JSON,default=dict)

class AuditLog(UUIDTimestampMixin, Base):
    __tablename__="audit_logs"
    brand_id: Mapped[uuid.UUID|None]=mapped_column(ForeignKey("brands.id",ondelete="SET NULL"),nullable=True,index=True)
    actor_id: Mapped[uuid.UUID|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),nullable=True)
    action: Mapped[str]=mapped_column(String(80))
    entity_type: Mapped[str]=mapped_column(String(80))
    entity_id: Mapped[str|None]=mapped_column(String(80),nullable=True)
    details: Mapped[dict]=mapped_column(JSON,default=dict)
    ip_address: Mapped[str|None]=mapped_column(String(64),nullable=True)


class Employee(UUIDTimestampMixin, Base):
    __tablename__="employees"
    brand_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("brands.id",ondelete="CASCADE"),index=True)
    branch_id: Mapped[uuid.UUID|None]=mapped_column(ForeignKey("branches.id",ondelete="SET NULL"),nullable=True,index=True)
    name: Mapped[str]=mapped_column(String(120))
    email: Mapped[str]=mapped_column(String(190),index=True)
    phone: Mapped[str|None]=mapped_column(String(32),nullable=True)
    role: Mapped[str]=mapped_column(String(40),default="cashier")
    permissions: Mapped[dict]=mapped_column(JSON,default=dict)
    pin_hash: Mapped[str|None]=mapped_column(String(255),nullable=True)
    is_active: Mapped[bool]=mapped_column(Boolean,default=True)
    __table_args__=(UniqueConstraint("brand_id","email",name="uq_employee_brand_email"),)

class MembershipTier(UUIDTimestampMixin, Base):
    __tablename__="membership_tiers"
    brand_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("brands.id",ondelete="CASCADE"),index=True)
    name: Mapped[str]=mapped_column(String(100))
    rank: Mapped[int]=mapped_column(Integer,default=0)
    color: Mapped[str]=mapped_column(String(7),default="#C6FF4A")
    min_points: Mapped[int]=mapped_column(Integer,default=0)
    min_spend: Mapped[int]=mapped_column(Integer,default=0)
    points_multiplier: Mapped[int]=mapped_column(Integer,default=1)
    benefits: Mapped[dict]=mapped_column(JSON,default=dict)
    is_active: Mapped[bool]=mapped_column(Boolean,default=True)

class Reward(UUIDTimestampMixin, Base):
    __tablename__="rewards"
    brand_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("brands.id",ondelete="CASCADE"),index=True)
    name: Mapped[str]=mapped_column(String(160))
    description: Mapped[str|None]=mapped_column(Text,nullable=True)
    points_cost: Mapped[int]=mapped_column(Integer,default=100)
    stock: Mapped[int|None]=mapped_column(Integer,nullable=True)
    image_url: Mapped[str|None]=mapped_column(Text,nullable=True)
    is_active: Mapped[bool]=mapped_column(Boolean,default=True)

class StampProgram(UUIDTimestampMixin, Base):
    __tablename__="stamp_programs"
    brand_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("brands.id",ondelete="CASCADE"),index=True)
    name: Mapped[str]=mapped_column(String(160))
    required_stamps: Mapped[int]=mapped_column(Integer,default=10)
    reward_title: Mapped[str]=mapped_column(String(160),default="مكافأة مجانية")
    stamp_icon: Mapped[str]=mapped_column(String(40),default="star")
    is_active: Mapped[bool]=mapped_column(Boolean,default=True)

class WalletCertificate(UUIDTimestampMixin, Base):
    __tablename__="wallet_certificates"
    brand_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("brands.id",ondelete="CASCADE"),index=True)
    filename: Mapped[str]=mapped_column(String(255))
    storage_path: Mapped[str]=mapped_column(Text)
    certificate_type: Mapped[str]=mapped_column(String(30),default="p12")
    expires_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    status: Mapped[str]=mapped_column(String(30),default="uploaded")

class WalletPass(UUIDTimestampMixin, Base):
    __tablename__="wallet_passes"
    brand_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("brands.id",ondelete="CASCADE"),index=True)
    customer_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("customers.id",ondelete="CASCADE"),index=True)
    serial_number: Mapped[str]=mapped_column(String(100),unique=True,index=True)
    public_token: Mapped[str]=mapped_column(String(100),unique=True,index=True)
    status: Mapped[str]=mapped_column(String(30),default="active")
    last_generated_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
