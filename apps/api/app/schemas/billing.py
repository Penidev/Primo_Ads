"""Billing / wallet schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class WalletBalance(BaseModel):
    balance_credits: float
    usd_per_credit: float
    estimated_usd_value: float


class TransactionEntry(BaseModel):
    id: uuid.UUID
    amount: float
    balance_after: float
    transaction_type: str
    description: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PlanPublic(BaseModel):
    slug: str
    display_name: str | None = None
    price_usd: float
    credits_per_month: int
    billing_interval: str
    features: dict | None = None

    model_config = {"from_attributes": True}


class PackagePublic(BaseModel):
    slug: str
    display_name: str | None = None
    price_usd: float
    credits: int
    bonus_credits: int

    model_config = {"from_attributes": True}


class CheckoutCreateRequest(BaseModel):
    """Buy either a credit package or a subscription plan (exactly one)."""

    gateway: Literal["stripe", "paypal", "cozzipay"]
    package_slug: str | None = Field(default=None, max_length=50)
    plan_slug: str | None = Field(default=None, max_length=50)


class CheckoutResponse(BaseModel):
    gateway: str
    session_id: str
    checkout_url: str
