"""Video model registry — drives the multi-model aggregator."""

from sqlalchemy import ARRAY, Boolean, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class VideoModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "video_models"

    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    api_endpoint: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    max_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supported_resolutions: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    supported_aspect_ratios: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    supports_audio: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supports_image_reference: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supports_video_extension: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    cost_per_second_usd: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    credit_multiplier: Mapped[float] = mapped_column(Numeric(4, 2), default=1.0, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    quality_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    avg_generation_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
