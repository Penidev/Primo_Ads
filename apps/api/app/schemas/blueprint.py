"""Ad blueprint schemas.

A blueprint is the structured deconstruction of a reference advertisement. It
captures *structure and psychology* only — never reproducible copy, footage
references, or brand assets — so generated output can learn patterns without
imitating a specific ad (Requirement 6.5).
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AD_CATEGORIES = (
    "problem-agitation-solution",
    "us-vs-competitor",
    "social-proof",
    "high-energy-disruptor",
    "emotional-storytelling",
    "product-demo",
)


class BlueprintBeat(BaseModel):
    """One structural beat of the reference ad."""

    beat_number: int = Field(ge=1, le=50)
    label: str = Field(max_length=100)  # e.g. "Hook", "Agitation"
    start_second: float = Field(ge=0, le=600)
    end_second: float = Field(ge=0, le=600)
    narrative_function: str = Field(max_length=1000)
    visual_technique: str = Field(max_length=1000)
    # Deliberately a paraphrase of intent, not a transcript.
    message_intent: str = Field(max_length=1000)


class BlueprintAnalysis(BaseModel):
    """Strict validation target for the model's video analysis."""

    suggested_title: str = Field(max_length=200)
    industry: str = Field(max_length=100)
    ad_category: str = Field(max_length=100)
    psychological_triggers: list[str] = Field(default_factory=list, max_length=12)
    hook_style: str = Field(max_length=100)
    pacing: str = Field(max_length=50)
    duration_seconds: int = Field(ge=1, le=600)
    format: str = Field(max_length=10)
    color_palette: list[str] = Field(default_factory=list, max_length=10)
    camera_techniques: list[str] = Field(default_factory=list, max_length=15)
    beats: list[BlueprintBeat] = Field(min_length=1, max_length=50)
    why_it_works: str = Field(max_length=3000)
    reusable_pattern: str = Field(max_length=3000)


class BlueprintCreateFromUrl(BaseModel):
    """Queue an analysis of a reference ad already reachable by URL."""

    source_url: str = Field(min_length=8, max_length=2000)
    industry_hint: str | None = Field(default=None, max_length=100)
    category_hint: str | None = Field(default=None, max_length=100)


class BlueprintUpdate(BaseModel):
    """Curator edits before approval."""

    title: str | None = Field(default=None, max_length=255)
    industry: str | None = Field(default=None, max_length=100)
    ad_category: str | None = Field(default=None, max_length=100)
    psychological_triggers: list[str] | None = Field(default=None, max_length=12)
    hook_style: str | None = Field(default=None, max_length=100)
    pacing: str | None = Field(default=None, max_length=50)
    format: str | None = Field(default=None, max_length=10)
    platform: str | None = Field(default=None, max_length=50)
    effectiveness_score: float | None = Field(default=None, ge=0, le=10)


class BlueprintApproval(BaseModel):
    is_approved: bool
    effectiveness_score: float | None = Field(default=None, ge=0, le=10)


class BlueprintSummary(BaseModel):
    id: uuid.UUID
    title: str | None = None
    industry: str | None = None
    ad_category: str | None = None
    duration_seconds: int | None = None
    format: str | None = None
    pacing: str | None = None
    hook_style: str | None = None
    effectiveness_score: float | None = None
    is_approved: bool
    has_embedding: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class BlueprintDetail(BlueprintSummary):
    psychological_triggers: list[str] | None = None
    camera_techniques: list[str] | None = None
    color_palette: list[str] | None = None
    structural_arc: dict | None = None
    full_analysis: str | None = None
    platform: str | None = None


class BlueprintStats(BaseModel):
    """Coverage view so curators can see where the library is thin."""

    total: int
    approved: int
    pending: int
    with_embeddings: int
    by_category: dict[str, int]
    by_industry: dict[str, int]


class AnalysisJobResult(BaseModel):
    blueprint_id: uuid.UUID
    status: Literal["analyzed", "failed"]
    detail: str | None = None
