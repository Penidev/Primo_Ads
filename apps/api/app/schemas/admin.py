"""Admin schemas for pricing, models, and user management."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# ---------- pricing ----------


class CreditRatioUpdate(BaseModel):
    """The single anchor that converts credits to money."""

    usd_per_credit: float = Field(gt=0, le=1000)


class ActionPricingUpdate(BaseModel):
    base_credits: float | None = Field(default=None, ge=0, le=10000)
    display_name: str | None = Field(default=None, max_length=150)
    is_enabled: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)


class ActionPricingAdmin(BaseModel):
    action_key: str
    display_name: str | None = None
    base_credits: float
    unit: str | None = None
    is_enabled: bool
    notes: str | None = None
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------- video models ----------


class VideoModelUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    credit_multiplier: float | None = Field(default=None, gt=0, le=100)
    cost_per_second_usd: float | None = Field(default=None, ge=0, le=100)
    is_enabled: bool | None = None
    quality_tier: str | None = Field(default=None, max_length=20)


class VideoModelCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=50, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    display_name: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=50)
    model_id: str = Field(min_length=1, max_length=200)
    max_duration_seconds: int = Field(default=8, ge=1, le=300)
    supported_resolutions: list[str] = Field(default_factory=lambda: ["1080p"])
    supported_aspect_ratios: list[str] = Field(default_factory=lambda: ["9:16", "16:9"])
    supports_audio: bool = False
    supports_image_reference: bool = True
    cost_per_second_usd: float = Field(ge=0, le=100)
    credit_multiplier: float = Field(default=1.0, gt=0, le=100)
    quality_tier: str = Field(default="standard", max_length=20)


class VideoModelAdmin(BaseModel):
    """Full registry row, including the margin analysis admins need."""

    slug: str
    display_name: str | None = None
    provider: str | None = None
    model_id: str | None = None
    is_enabled: bool
    quality_tier: str | None = None
    supports_audio: bool
    supports_image_reference: bool
    max_duration_seconds: int | None = None
    cost_per_second_usd: float | None = None
    credit_multiplier: float

    model_config = {"from_attributes": True}


class ModelMargin(BaseModel):
    """Live margin so pricing is never set below provider cost."""

    slug: str
    display_name: str | None = None
    seconds_per_scene: int
    platform_cost_usd: float
    user_price_usd: float
    margin_usd: float
    margin_percent: float | None = None
    is_profitable: bool


# ---------- plans & packages ----------


class PlanUpsert(BaseModel):
    slug: str = Field(min_length=1, max_length=50, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    display_name: str = Field(min_length=1, max_length=100)
    price_usd: float = Field(ge=0, le=100000)
    credits_per_month: int = Field(ge=0, le=1000000)
    billing_interval: str = Field(default="monthly", max_length=20)
    is_enabled: bool = True
    sort_order: int = 0


class PackageUpsert(BaseModel):
    slug: str = Field(min_length=1, max_length=50, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    display_name: str = Field(min_length=1, max_length=100)
    price_usd: float = Field(ge=0, le=100000)
    credits: int = Field(ge=0, le=1000000)
    bonus_credits: int = Field(default=0, ge=0, le=1000000)
    is_enabled: bool = True
    sort_order: int = 0


# ---------- users & credits ----------


class UserAdmin(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None = None
    company_name: str | None = None
    country: str | None = None
    industry: str | None = None
    is_active: bool
    is_admin: bool
    onboarding_completed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserStatusUpdate(BaseModel):
    is_active: bool


class ManualCreditGrant(BaseModel):
    amount: float = Field(gt=0, le=100000)
    reason: str = Field(min_length=3, max_length=500)


# ---------- audit & security telemetry ----------


class AuditEntry(BaseModel):
    id: uuid.UUID
    actor_email: str | None = None
    action: str
    target_type: str | None = None
    target_id: str | None = None
    detail: dict | None = None
    ip_address: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SecurityEventEntry(BaseModel):
    id: uuid.UUID
    event_type: str
    severity: str
    ip_address: str | None = None
    description: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertEntry(BaseModel):
    event_type: str
    label: str
    count: int
    threshold: int
    window_minutes: int


# ---------- feature flags ----------


class FeatureFlagUpdate(BaseModel):
    is_enabled: bool
    applies_to: str | None = Field(default=None, max_length=100)


class FeatureFlagAdmin(BaseModel):
    key: str
    description: str | None = None
    is_enabled: bool
    applies_to: str

    model_config = {"from_attributes": True}
