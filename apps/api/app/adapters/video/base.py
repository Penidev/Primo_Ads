"""Video generation adapter interface.

Every provider is reached through this one interface, so adding a model means
adding a registry row (and, for a new provider, one adapter class) rather than
touching the pipeline or the frontend (ARCHITECTURE.md Module 6).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class VideoGenConfig:
    """Provider-agnostic generation request."""

    model_id: str
    prompt: str
    aspect_ratio: str = "9:16"
    duration_seconds: int = 6
    resolution: str = "1080p"
    reference_image_urls: list[str] = field(default_factory=list)
    generate_audio: bool = True
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class VideoGenSubmission:
    """Handle returned when a generation is accepted by the provider."""

    provider: str
    provider_job_id: str


@dataclass(frozen=True)
class VideoGenStatus:
    state: JobState
    video_url: str | None = None
    error_message: str | None = None


class VideoProviderError(Exception):
    """Provider call failed. Message is safe to log (no secrets)."""


class VideoModelAdapter(ABC):
    """Adapter contract for a video generation provider."""

    provider_name: str

    @abstractmethod
    async def submit(self, config: VideoGenConfig) -> VideoGenSubmission:
        """Start a generation and return its provider job handle."""

    @abstractmethod
    async def check_status(self, provider_job_id: str) -> VideoGenStatus:
        """Poll a previously submitted generation."""
