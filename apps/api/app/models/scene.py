"""Scene and SceneAsset models — the per-scene units of a project."""

import uuid

from sqlalchemy import ARRAY, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Scene(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scenes"
    __table_args__ = (UniqueConstraint("project_id", "scene_number"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scene_number: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    script_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    compiled_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_image_urls: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    video_url: Mapped[str | None] = mapped_column(String, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String, nullable=True)

    # pending -> generating -> completed / failed  (per-scene resumability)
    generation_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    generation_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_slug: Mapped[str | None] = mapped_column(String(50), nullable=True)
    generation_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class SceneAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scene_assets"

    scene_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scenes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)

    # pending -> generated -> approved / rejected / user_uploaded
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
