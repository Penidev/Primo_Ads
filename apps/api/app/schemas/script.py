"""Generated-script schemas.

These double as validation of LLM output: the model's JSON is parsed into these
models before anything downstream uses it, so malformed or injected content is
rejected rather than flowing into the pipeline (SECURITY.md §4).
"""

from typing import Literal

from pydantic import BaseModel, Field

AspectRatio = Literal["9:16", "16:9", "1:1"]


class AssetRequirement(BaseModel):
    asset_type: str = Field(max_length=50)
    description: str = Field(max_length=2000)
    style: str | None = Field(default=None, max_length=500)


class SceneScript(BaseModel):
    scene_number: int = Field(ge=1, le=50)
    scene_label: str | None = Field(default=None, max_length=100)
    duration_seconds: int = Field(ge=1, le=60)
    script_text: str = Field(default="", max_length=2000)
    voiceover_direction: str | None = Field(default=None, max_length=1000)
    visual_description: str = Field(max_length=4000)
    camera_movement: str | None = Field(default=None, max_length=500)
    color_grading: str | None = Field(default=None, max_length=500)
    lighting: str | None = Field(default=None, max_length=500)
    audio_sfx: str | None = Field(default=None, max_length=500)
    graphics_overlay: str | None = Field(default=None, max_length=1000)
    brand_elements: str | None = Field(default=None, max_length=1000)
    video_prompt: str = Field(max_length=4000)
    image_gen_needed: list[AssetRequirement] = Field(default_factory=list, max_length=10)


class GeneratedScript(BaseModel):
    campaign_title: str = Field(max_length=200)
    total_duration_seconds: int = Field(ge=1, le=300)
    scenes: list[SceneScript] = Field(min_length=1, max_length=50)
    music_direction: str | None = Field(default=None, max_length=1000)
    overall_color_palette: str | None = Field(default=None, max_length=500)
    target_emotion_arc: str | None = Field(default=None, max_length=500)


class ScriptGenerateRequest(BaseModel):
    """Optional overrides at generation time; the brief supplies the rest."""

    ad_category: str | None = Field(default=None, max_length=100)
    aspect_ratio: AspectRatio | None = None
    target_duration_seconds: int | None = Field(default=None, ge=5, le=180)


class ScriptCostPreview(BaseModel):
    credits_required: float
    estimated_usd: float
    current_balance: float
    sufficient: bool
