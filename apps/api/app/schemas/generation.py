"""Video generation request/response schemas."""

import uuid

from pydantic import BaseModel, Field


class StartGenerationRequest(BaseModel):
    model_slug: str = Field(min_length=1, max_length=50)


class RerollRequest(BaseModel):
    model_slug: str | None = Field(default=None, max_length=50)


class ScenePublic(BaseModel):
    id: uuid.UUID
    scene_number: int
    duration_seconds: int | None = None
    generation_status: str
    model_slug: str | None = None
    video_url: str | None = None
    thumbnail_url: str | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}


class GenerationState(BaseModel):
    project_status: str
    selected_model_slug: str | None = None
    final_video_url: str | None = None
    scenes: list[ScenePublic]
