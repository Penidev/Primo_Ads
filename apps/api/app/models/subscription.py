"""User subscription model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    tier: Mapped[str] = mapped_column(String(50), nullable=False)
    # active / cancelled / past_due / paused
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    gateway: Mapped[str] = mapped_column(String(50), nullable=False)  # stripe/paypal/cozzipay
    gateway_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credits_per_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
