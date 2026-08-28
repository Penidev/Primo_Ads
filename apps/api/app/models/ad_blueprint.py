"""Ad blueprint model — the analyzed swipe-file entries used for RAG."""

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Boolean, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

# OpenAI/Gemini text-embedding dimension used for similarity search.
EMBEDDING_DIM = 1536


class AdBlueprint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ad_blueprints"

    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_video_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # internal only
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ad_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    psychological_triggers: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    structural_arc: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    format: Mapped[str | None] = mapped_column(String(10), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hook_style: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pacing: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color_palette: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    camera_techniques: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    effectiveness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    full_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
