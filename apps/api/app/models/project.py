"""Project model — one advertising project per row."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # State machine drives resume: draft -> scripted -> assets_ready
    #                              -> generating -> completed / failed
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)

    brief: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    script: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    selected_model_slug: Mapped[str | None] = mapped_column(String(50), nullable=True)
    total_credits_spent: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    final_video_url: Mapped[str | None] = mapped_column(String, nullable=True)

    # Soft delete — 30-day recovery window before permanent removal
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
