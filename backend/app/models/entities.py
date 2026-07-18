import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDTimestampMixin


class User(UUIDTimestampMixin, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(190), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default="platform_owner", index=True)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("brands.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuthSession(UUIDTimestampMixin, Base):
    __tablename__ = "auth_sessions"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Brand(UUIDTimestampMixin, Base):
    __tablename__ = "brands"
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_color: Mapped[str] = mapped_column(String(7), default="#111827")
    accent_color: Mapped[str] = mapped_column(String(7), default="#C6FF4A")
    currency: Mapped[str] = mapped_column(String(8), default="QAR")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Qatar")
    locale: Mapped[str] = mapped_column(String(12), default="ar")
    program_mode: Mapped[str] = mapped_column(String(30), default="full", index=True)
    feature_flags: Mapped[dict] = mapped_column(JSON, default=dict)
    join_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    join_require_email: Mapped[bool] = mapped_column(Boolean, default=False)
    join_welcome_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    branches = relationship("Branch", cascade="all, delete-orphan")


class UserBrandAccess(UUIDTimestampMixin, Base):
    __tablename__ = "user_brand_access"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(30), default="brand_admin")
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("user_id", "brand_id", name="uq_user_brand_access"),)


class Branch(UUIDTimestampMixin, Base):
    __tablename__ = "branches"
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    manager_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    latitude: Mapped[str | None] = mapped_column(String(32), nullable=True)
    longitude: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Employee(UUIDTimestampMixin, Base):
    __tablename__ = "employees"
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(190), index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    role: Mapped[str] = mapped_column(String(40), default="employee")
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)
    pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("brand_id", "email", name="uq_employee_brand_email"),)


class Customer(UUIDTimestampMixin, Base):
    __tablename__ = "customers"
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    home_branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(190), nullable=True)
    birthday: Mapped[date | None] = mapped_column(Date, nullable=True)
    membership_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    points: Mapped[int] = mapped_column(Integer, default=0)
    stamps: Mapped[int] = mapped_column(Integer, default=0)
    available_rewards: Mapped[int] = mapped_column(Integer, default=0)
    tier: Mapped[str] = mapped_column(String(60), default="bronze")
    visits: Mapped[int] = mapped_column(Integer, default=0)
    total_spend: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    last_visit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("brand_id", "phone", name="uq_customer_brand_phone"),)


class MembershipTier(UUIDTimestampMixin, Base):
    __tablename__ = "membership_tiers"
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    rank: Mapped[int] = mapped_column(Integer, default=0)
    color: Mapped[str] = mapped_column(String(7), default="#C6FF4A")
    min_points: Mapped[int] = mapped_column(Integer, default=0)
    min_spend: Mapped[int] = mapped_column(Integer, default=0)
    points_multiplier: Mapped[int] = mapped_column(Integer, default=1)
    benefits: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class LoyaltyProgram(UUIDTimestampMixin, Base):
    __tablename__ = "loyalty_programs"
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    program_type: Mapped[str] = mapped_column(String(30), default="hybrid")
    points_per_visit: Mapped[int] = mapped_column(Integer, default=10)
    points_per_currency: Mapped[int] = mapped_column(Integer, default=1)
    required_stamps: Mapped[int] = mapped_column(Integer, default=6)
    stamp_reward_title: Mapped[str] = mapped_column(String(160), default="مكافأة مجانية")
    reward_points: Mapped[int] = mapped_column(Integer, default=100)
    reward_title: Mapped[str] = mapped_column(String(160), default="مكافأة مجانية")
    birthday_bonus: Mapped[int] = mapped_column(Integer, default=0)
    referral_bonus: Mapped[int] = mapped_column(Integer, default=0)
    cashback_percent: Mapped[int] = mapped_column(Integer, default=0)
    points_expiry_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    daily_points_cap: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allow_manual_adjustment: Mapped[bool] = mapped_column(Boolean, default=True)
    rules: Mapped[dict] = mapped_column(JSON, default=dict)


class LoyaltyTransaction(UUIDTimestampMixin, Base):
    __tablename__ = "loyalty_transactions"
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(40), index=True)
    delta_points: Mapped[int] = mapped_column(Integer, default=0)
    delta_stamps: Mapped[int] = mapped_column(Integer, default=0)
    points_before: Mapped[int] = mapped_column(Integer, default=0)
    points_after: Mapped[int] = mapped_column(Integer, default=0)
    stamps_before: Mapped[int] = mapped_column(Integer, default=0)
    stamps_after: Mapped[int] = mapped_column(Integer, default=0)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    remaining_points: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class Reward(UUIDTimestampMixin, Base):
    __tablename__ = "rewards"
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    points_cost: Mapped[int] = mapped_column(Integer, default=100)
    stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Coupon(UUIDTimestampMixin, Base):
    __tablename__ = "coupons"
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reward_type: Mapped[str] = mapped_column(String(30), default="points")
    reward_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_redemptions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    per_customer_limit: Mapped[int] = mapped_column(Integer, default=1)
    redemption_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("brand_id", "code", name="uq_coupon_brand_code"),)


class CouponRedemption(UUIDTimestampMixin, Base):
    __tablename__ = "coupon_redemptions"
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    coupon_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("coupons.id", ondelete="RESTRICT"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    benefit: Mapped[dict] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)


class StampProgram(UUIDTimestampMixin, Base):
    __tablename__ = "stamp_programs"
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_stamps: Mapped[int] = mapped_column(Integer, default=10)
    reward_title: Mapped[str] = mapped_column(String(160), default="مكافأة مجانية")
    reward_type: Mapped[str] = mapped_column(String(30), default="free_item")
    stamp_icon: Mapped[str] = mapped_column(String(40), default="coffee")
    background_color: Mapped[str] = mapped_column(String(7), default="#111827")
    accent_color: Mapped[str] = mapped_column(String(7), default="#C6FF4A")
    card_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    empty_stamp_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    filled_stamp_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("brand_id", "slug", name="uq_stamp_program_brand_slug"),)


class CustomerStampCard(UUIDTimestampMixin, Base):
    __tablename__ = "customer_stamp_cards"
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    stamp_program_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stamp_programs.id", ondelete="CASCADE"), index=True)
    stamps: Mapped[int] = mapped_column(Integer, default=0)
    rewards_available: Mapped[int] = mapped_column(Integer, default=0)
    lifetime_stamps: Mapped[int] = mapped_column(Integer, default=0)
    last_stamp_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("customer_id", "stamp_program_id", name="uq_customer_stamp_program"),)


class StampTransaction(UUIDTimestampMixin, Base):
    __tablename__ = "stamp_transactions"
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    stamp_program_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stamp_programs.id", ondelete="RESTRICT"), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(30), index=True)
    delta_stamps: Mapped[int] = mapped_column(Integer, default=0)
    stamps_before: Mapped[int] = mapped_column(Integer, default=0)
    stamps_after: Mapped[int] = mapped_column(Integer, default=0)
    delta_rewards: Mapped[int] = mapped_column(Integer, default=0)
    rewards_before: Mapped[int] = mapped_column(Integer, default=0)
    rewards_after: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class BrandWalletDesign(UUIDTimestampMixin, Base):
    __tablename__ = "brand_wallet_designs"
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), unique=True, index=True)
    background_color: Mapped[str] = mapped_column(String(7), default="#111827")
    foreground_color: Mapped[str] = mapped_column(String(7), default="#FFFFFF")
    label_color: Mapped[str] = mapped_column(String(7), default="#C6FF4A")
    logo_text: Mapped[str] = mapped_column(String(120), default="LOYALYN")
    card_title: Mapped[str] = mapped_column(String(120), default="بطاقة الولاء")
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    hero_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    background_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    strip_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    layout_style: Mapped[str] = mapped_column(String(30), default="classic")
    overlay_opacity: Mapped[int] = mapped_column(Integer, default=25)
    barcode_format: Mapped[str] = mapped_column(String(40), default="PKBarcodeFormatQR")
    fields: Mapped[dict] = mapped_column(JSON, default=dict)
    terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_version: Mapped[int] = mapped_column(Integer, default=1)
    published_version: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)


class PlatformWalletCredential(UUIDTimestampMixin, Base):
    __tablename__ = "platform_wallet_credentials"
    filename: Mapped[str] = mapped_column(String(255))
    p12_path: Mapped[str] = mapped_column(Text)
    wwdr_path: Mapped[str] = mapped_column(Text)
    encrypted_password: Mapped[str] = mapped_column(Text)
    pass_type_identifier: Mapped[str] = mapped_column(String(180), index=True)
    team_identifier: Mapped[str] = mapped_column(String(32))
    organization_name: Mapped[str] = mapped_column(String(160), default="Loyalyn")
    certificate_subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class WalletPass(UUIDTimestampMixin, Base):
    __tablename__ = "wallet_passes"
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    serial_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    public_token: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    authentication_token: Mapped[str] = mapped_column(String(100), unique=True)
    pass_type_identifier: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="active")
    update_tag: Mapped[int] = mapped_column(Integer, default=1, index=True)
    last_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_push_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("brand_id", "customer_id", name="uq_wallet_pass_customer"),)


class WalletDevice(UUIDTimestampMixin, Base):
    __tablename__ = "wallet_devices"
    device_library_identifier: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    push_token: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class WalletRegistration(UUIDTimestampMixin, Base):
    __tablename__ = "wallet_registrations"
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("wallet_devices.id", ondelete="CASCADE"), index=True)
    pass_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("wallet_passes.id", ondelete="CASCADE"), index=True)
    __table_args__ = (UniqueConstraint("device_id", "pass_id", name="uq_wallet_registration"),)


class NotificationTemplate(UUIDTimestampMixin, Base):
    __tablename__ = "notification_templates"
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(30), default="in_app")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class NotificationCampaign(UUIDTimestampMixin, Base):
    __tablename__ = "notification_campaigns"
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(30), default="in_app")
    audience_type: Mapped[str] = mapped_column(String(30), default="all")
    audience_filter: Mapped[dict] = mapped_column(JSON, default=dict)
    recurrence: Mapped[str] = mapped_column(String(20), default="none")
    series_key: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_recipients: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)


class NotificationRecipient(UUIDTimestampMixin, Base):
    __tablename__ = "notification_recipients"
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("notification_campaigns.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(190), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("campaign_id", "customer_id", name="uq_campaign_recipient"),)


class Notification(UUIDTimestampMixin, Base):
    __tablename__ = "notifications"
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=True, index=True)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("notification_campaigns.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(30), default="in_app")
    audience: Mapped[str] = mapped_column(String(30), default="individual")
    status: Mapped[str] = mapped_column(String(30), default="sent")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)


class AuditLog(UUIDTimestampMixin, Base):
    __tablename__ = "audit_logs"
    brand_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("brands.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
