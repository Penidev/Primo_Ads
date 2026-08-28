"""Project and brief schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    brief: dict[str, Any] = Field(default_factory=dict)


class ProjectBriefUpdate(BaseModel):
    """Auto-save payload — partial brief merges are allowed."""

    title: str | None = Field(default=None, max_length=255)
    brief: dict[str, Any] | None = None


class ProjectSummary(BaseModel):
    """Row shown in the project folder / dashboard list."""

    id: uuid.UUID
    title: str | None = None
    status: str
    total_credits_spent: float
    final_video_url: str | None = None
    updated_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectDetail(ProjectSummary):
    brief: dict[str, Any]
    script: dict[str, Any] | None = None
    selected_model_slug: str | None = None
