from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator


class Login(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=200)


class BrandCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(pattern=r"^[a-z0-9-]+$", min_length=2, max_length=80)
    primary_color: str = Field(default="#111827", pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_color: str = Field(default="#C6FF4A", pattern=r"^#[0-9A-Fa-f]{6}$")
    currency: str = Field(default="QAR", min_length=3, max_length=8)
    timezone: str = Field(default="Asia/Qatar", max_length=64)
    locale: str = Field(default="ar", max_length=12)
    program_mode: str = Field(default="full", pattern=r"^(stamps_only|points_only|stamps_points|full|custom)$")
    feature_flags: dict = Field(default_factory=dict)
    join_enabled: bool = True
    join_require_email: bool = False
    join_welcome_text: str | None = Field(default=None, max_length=1000)
    manager_name: str | None = Field(default=None, max_length=120)
    manager_email: EmailStr | None = None
    manager_password: str | None = Field(default=None, min_length=8, max_length=200)

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        return value.strip().lower()


class BrandUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    logo_url: str | None = None
    primary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    currency: str | None = Field(default=None, min_length=3, max_length=8)
    timezone: str | None = Field(default=None, max_length=64)
    locale: str | None = Field(default=None, max_length=12)
    program_mode: str | None = Field(default=None, pattern=r"^(stamps_only|points_only|stamps_points|full|custom)$")
    feature_flags: dict | None = None
    join_enabled: bool | None = None
    join_require_email: bool | None = None
    join_welcome_text: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None


class BranchCreate(BaseModel):
    brand_id: UUID
    name: str = Field(min_length=2, max_length=120)
    address: str | None = None
    phone: str | None = Field(default=None, max_length=32)
    manager_name: str | None = Field(default=None, max_length=120)
    latitude: str | None = None
    longitude: str | None = None


class BranchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    address: str | None = None
    phone: str | None = None
    manager_name: str | None = None
    latitude: str | None = None
    longitude: str | None = None
    is_active: bool | None = None


class StaffCreate(BaseModel):
    brand_id: UUID
    branch_id: UUID | None = None
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str | None = None
    role: str = Field(default="employee", pattern=r"^(brand_admin|manager|employee)$")
    password: str = Field(min_length=8, max_length=200)
    permissions: dict = Field(default_factory=dict)


class StaffUpdate(BaseModel):
    branch_id: UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = None
    role: str | None = Field(default=None, pattern=r"^(brand_admin|manager|employee)$")
    permissions: dict | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=200)


class CustomerCreate(BaseModel):
    brand_id: UUID
    card_template_id: UUID | None = None
    home_branch_id: UUID | None = None
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=5, max_length=32)
    email: EmailStr | None = None
    birthday: date | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None


class CustomerUpdate(BaseModel):
    home_branch_id: UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, min_length=5, max_length=32)
    email: EmailStr | None = None
    birthday: date | None = None
    tags: list[str] | None = None
    notes: str | None = None
    is_active: bool | None = None


class LoyaltyProgramUpdate(BaseModel):
    enabled: bool = True
    program_type: str = Field(default="hybrid", pattern=r"^(points|stamps|hybrid|cashback)$")
    points_per_visit: int = Field(default=10, ge=0, le=100000)
    points_per_currency: int = Field(default=1, ge=0, le=10000)
    required_stamps: int = Field(default=6, ge=1, le=100)
    stamp_reward_title: str = Field(default="مكافأة مجانية", max_length=160)
    reward_points: int = Field(default=100, ge=1, le=1000000)
    reward_title: str = Field(default="مكافأة مجانية", max_length=160)
    birthday_bonus: int = Field(default=0, ge=0, le=100000)
    referral_bonus: int = Field(default=0, ge=0, le=100000)
    cashback_percent: int = Field(default=0, ge=0, le=100)
    points_expiry_days: int | None = Field(default=None, ge=1, le=3650)
    daily_points_cap: int | None = Field(default=None, ge=1, le=10000000)
    allow_manual_adjustment: bool = True
    rules: dict = Field(default_factory=dict)


class LoyaltyApply(BaseModel):
    action: str = Field(pattern=r"^(visit|spend|manual|birthday|referral|reversal)$")
    branch_id: UUID | None = None
    amount: Decimal = Field(default=Decimal("0"), ge=0)
    points: int = Field(default=0, ge=-1000000, le=1000000)
    stamps: int = Field(default=0, ge=-1000, le=1000)
    note: str | None = Field(default=None, max_length=500)
    reference: str | None = Field(default=None, max_length=120)
    idempotency_key: str = Field(min_length=8, max_length=100)


class TierCreate(BaseModel):
    brand_id: UUID
    name: str = Field(min_length=2, max_length=100)
    rank: int = Field(default=0, ge=0, le=100)
    color: str = Field(default="#C6FF4A", pattern=r"^#[0-9A-Fa-f]{6}$")
    min_points: int = Field(default=0, ge=0)
    min_spend: int = Field(default=0, ge=0)
    points_multiplier: int = Field(default=1, ge=1, le=100)
    benefits: dict = Field(default_factory=dict)




class TierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    rank: int | None = Field(default=None, ge=0, le=100)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    min_points: int | None = Field(default=None, ge=0)
    min_spend: int | None = Field(default=None, ge=0)
    points_multiplier: int | None = Field(default=None, ge=1, le=100)
    benefits: dict | None = None
    is_active: bool | None = None


class RewardCreate(BaseModel):
    brand_id: UUID
    name: str = Field(min_length=2, max_length=160)
    description: str | None = None
    points_cost: int = Field(ge=0, le=10000000)
    stock: int | None = Field(default=None, ge=0)
    image_url: str | None = None




class RewardUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = None
    points_cost: int | None = Field(default=None, ge=0, le=10000000)
    stock: int | None = Field(default=None, ge=0)
    image_url: str | None = None
    is_active: bool | None = None


class RewardRedeem(BaseModel):
    reward_id: UUID
    branch_id: UUID | None = None
    idempotency_key: str = Field(min_length=8, max_length=100)


class WalletDesignUpdate(BaseModel):
    background_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    foreground_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    label_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    logo_text: str = Field(min_length=1, max_length=120)
    card_title: str = Field(min_length=1, max_length=120)
    logo_url: str | None = None
    hero_url: str | None = None
    background_image_url: str | None = None
    strip_url: str | None = None
    layout_style: str = Field(default="classic", pattern=r"^(classic|visual|minimal)$")
    overlay_opacity: int = Field(default=25, ge=0, le=90)
    barcode_format: str = Field(default="PKBarcodeFormatQR", pattern=r"^(PKBarcodeFormatQR|PKBarcodeFormatPDF417|PKBarcodeFormatAztec|PKBarcodeFormatCode128)$")
    fields: dict = Field(default_factory=dict)
    terms: str | None = None


class CampaignCreate(BaseModel):
    brand_id: UUID
    name: str = Field(min_length=2, max_length=160)
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=3000)
    channel: str = Field(default="in_app", pattern=r"^(in_app|wallet_push|email|sms|webhook)$")
    audience_type: str = Field(default="all", pattern=r"^(all|tier|min_points|inactive_days|birthday|selected|branch|rewards_ready)$")
    audience_filter: dict = Field(default_factory=dict)
    scheduled_at: datetime | None = None
    recurrence: str = Field(default="none", pattern=r"^(none|daily|weekly|monthly)$")
    send_now: bool = False


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    title: str | None = Field(default=None, min_length=1, max_length=160)
    body: str | None = Field(default=None, min_length=1, max_length=3000)
    channel: str | None = Field(default=None, pattern=r"^(in_app|wallet_push|email|sms|webhook)$")
    audience_type: str | None = Field(default=None, pattern=r"^(all|tier|min_points|inactive_days|birthday|selected|branch|rewards_ready)$")
    audience_filter: dict | None = None
    scheduled_at: datetime | None = None
    recurrence: str | None = Field(default=None, pattern=r"^(none|daily|weekly|monthly)$")


class NotificationTemplateCreate(BaseModel):
    brand_id: UUID
    name: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=3000)
    channel: str = Field(default="in_app", pattern=r"^(in_app|wallet_push|email|sms|webhook)$")


class WalletPushToken(BaseModel):
    pushToken: str


class EarnedRewardRedeem(BaseModel):
    branch_id: UUID | None = None
    idempotency_key: str = Field(min_length=8, max_length=100)


class TransactionReverse(BaseModel):
    reason: str = Field(min_length=2, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=100)


class CouponCreate(BaseModel):
    brand_id: UUID
    code: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=160)
    description: str | None = None
    reward_type: str = Field(pattern=r"^(points|stamps|discount_percent|discount_amount|free_item)$")
    reward_value: Decimal = Field(default=Decimal("0"), ge=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    max_redemptions: int | None = Field(default=None, ge=1)
    per_customer_limit: int = Field(default=1, ge=1, le=100)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class CouponUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = None
    reward_type: str | None = Field(default=None, pattern=r"^(points|stamps|discount_percent|discount_amount|free_item)$")
    reward_value: Decimal | None = Field(default=None, ge=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    max_redemptions: int | None = Field(default=None, ge=1)
    per_customer_limit: int | None = Field(default=None, ge=1, le=100)
    is_active: bool | None = None


class CouponRedeem(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    branch_id: UUID | None = None
    idempotency_key: str = Field(min_length=8, max_length=100)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class BrandProgramProfileUpdate(BaseModel):
    program_mode: str = Field(pattern=r"^(stamps_only|points_only|stamps_points|full|custom)$")
    feature_flags: dict = Field(default_factory=dict)
    join_enabled: bool = True
    join_require_email: bool = False
    join_welcome_text: str | None = Field(default=None, max_length=1000)


class StampProgramCreate(BaseModel):
    brand_id: UUID
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9-]+$", min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=1000)
    required_stamps: int = Field(default=10, ge=1, le=100)
    reward_title: str = Field(default="مكافأة مجانية", min_length=2, max_length=160)
    reward_type: str = Field(default="free_item", pattern=r"^(free_item|discount|custom)$")
    stamp_icon: str = Field(default="coffee", min_length=1, max_length=40)
    background_color: str = Field(default="#111827", pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_color: str = Field(default="#C6FF4A", pattern=r"^#[0-9A-Fa-f]{6}$")
    is_default: bool = False
    sort_order: int = Field(default=0, ge=0, le=1000)

    @field_validator("slug")
    @classmethod
    def normalize_stamp_slug(cls, value: str) -> str:
        return value.strip().lower()


class StampProgramUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9-]+$", min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=1000)
    required_stamps: int | None = Field(default=None, ge=1, le=100)
    reward_title: str | None = Field(default=None, min_length=2, max_length=160)
    reward_type: str | None = Field(default=None, pattern=r"^(free_item|discount|custom)$")
    stamp_icon: str | None = Field(default=None, min_length=1, max_length=40)
    background_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    is_default: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=1000)
    is_active: bool | None = None

    @field_validator("slug")
    @classmethod
    def normalize_optional_stamp_slug(cls, value: str | None) -> str | None:
        return value.strip().lower() if value else value


class StampAction(BaseModel):
    branch_id: UUID | None = None
    quantity: int = Field(default=1, ge=1, le=20)
    note: str | None = Field(default=None, max_length=500)
    reference: str | None = Field(default=None, max_length=120)
    idempotency_key: str = Field(min_length=8, max_length=100)


class StampRedeem(BaseModel):
    branch_id: UUID | None = None
    note: str | None = Field(default=None, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=100)


class PublicJoin(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=5, max_length=32)
    email: EmailStr | None = None
    birthday: date | None = None
    selected_card_template_id: UUID | None = None
    selected_program_ids: list[UUID] = Field(default_factory=list)

class CardTemplateCreate(BaseModel):
    brand_id: UUID
    name: str = Field(min_length=2, max_length=160)
    name_en: str | None = Field(default=None, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9-]+$", min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=1500)
    is_default: bool = False
    allow_public_join: bool = True
    sort_order: int = Field(default=0, ge=0, le=1000)
    program_ids: list[UUID] = Field(default_factory=list)
    background_color: str = Field(default="#111827", pattern=r"^#[0-9A-Fa-f]{6}$")
    foreground_color: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    label_color: str = Field(default="#C6FF4A", pattern=r"^#[0-9A-Fa-f]{6}$")
    logo_text: str = Field(default="LOYALYN", min_length=1, max_length=120)
    card_title: str = Field(default="بطاقة الولاء", min_length=1, max_length=120)
    layout_style: str = Field(default="classic", pattern=r"^(classic|visual|minimal)$")
    overlay_opacity: int = Field(default=25, ge=0, le=90)
    barcode_format: str = Field(default="PKBarcodeFormatQR", pattern=r"^(PKBarcodeFormatQR|PKBarcodeFormatPDF417|PKBarcodeFormatAztec|PKBarcodeFormatCode128)$")
    fields: dict = Field(default_factory=lambda: {"show_stamps": True, "show_rewards": True, "show_tier": False, "show_points": False, "show_visits": False})
    terms: str | None = None

    @field_validator("slug")
    @classmethod
    def normalize_card_template_slug(cls, value: str) -> str:
        return value.strip().lower()


class CardTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    name_en: str | None = Field(default=None, max_length=160)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9-]+$", min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=1500)
    is_default: bool | None = None
    allow_public_join: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=1000)
    program_ids: list[UUID] | None = None
    background_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    foreground_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    label_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    logo_text: str | None = Field(default=None, min_length=1, max_length=120)
    card_title: str | None = Field(default=None, min_length=1, max_length=120)
    layout_style: str | None = Field(default=None, pattern=r"^(classic|visual|minimal)$")
    overlay_opacity: int | None = Field(default=None, ge=0, le=90)
    barcode_format: str | None = Field(default=None, pattern=r"^(PKBarcodeFormatQR|PKBarcodeFormatPDF417|PKBarcodeFormatAztec|PKBarcodeFormatCode128)$")
    fields: dict | None = None
    terms: str | None = None

    @field_validator("slug")
    @classmethod
    def normalize_optional_card_template_slug(cls, value: str | None) -> str | None:
        return value.strip().lower() if value else value


class CustomerCardAssignmentUpdate(BaseModel):
    card_template_id: UUID


class StampTransactionReverse(BaseModel):
    reason: str = Field(min_length=2, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=100)
