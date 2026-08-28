"""Payment records: purchase intents and processed webhook events.

`CreditPurchase` is created before redirecting to a gateway and is the anchor
that fulfilment looks up, so a webhook can never invent an amount of credits.
`ProcessedWebhook` gives us idempotency: a repeated delivery is ignored rather
than credited twice (SECURITY.md §3).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class CreditPurchase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_purchases"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Our own reference sent to the gateway and echoed back in the webhook.
    reference: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    gateway: Mapped[str] = mapped_column(String(50), nullable=False)
    gateway_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    package_slug: Mapped[str | None] = mapped_column(String(50), nullable=True)
    plan_slug: Mapped[str | None] = mapped_column(String(50), nullable=True)
    amount_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)

    # pending -> completed / failed / expired
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProcessedWebhook(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "processed_webhooks"
    __table_args__ = (UniqueConstraint("gateway", "event_id", name="uq_webhook_gateway_event"),)

    gateway: Mapped[str] = mapped_column(String(50), nullable=False)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
