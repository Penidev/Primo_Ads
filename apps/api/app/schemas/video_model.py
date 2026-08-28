"""Video model registry schemas."""

from pydantic import BaseModel


class VideoModelPublic(BaseModel):
    """A selectable generation engine, as shown in the model picker."""

    slug: str
    display_name: str | None = None
    provider: str | None = None
    quality_tier: str | None = None
    max_duration_seconds: int | None = None
    supported_resolutions: list[str] | None = None
    supported_aspect_ratios: list[str] | None = None
    supports_audio: bool
    supports_image_reference: bool
    credit_multiplier: float
    avg_generation_time_seconds: int | None = None

    model_config = {"from_attributes": True}


class ModelCostPreview(BaseModel):
    model_slug: str
    scene_count: int
    credits_required: float
    estimated_usd: float
    current_balance: float
    sufficient: bool
