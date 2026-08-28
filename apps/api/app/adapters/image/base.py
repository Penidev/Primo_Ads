"""Image generation adapter interface.

Used to pre-generate brand-accurate reference frames before video generation, so
the video model has concrete visual anchors rather than having to imagine brand
elements (ARCHITECTURE.md Module 4).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ImageGenConfig:
    prompt: str
    aspect_ratio: str = "9:16"
    # Optional visual references (uploaded product shots, character sheets).
    reference_image_urls: list[str] = field(default_factory=list)
    seed: int | None = None
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ImageGenResult:
    image_url: str
    provider: str
    seed: int | None = None


class ImageProviderError(Exception):
    """Image provider call failed. Message is safe to log (no secrets)."""


class ImageAdapter(ABC):
    provider_name: str

    @abstractmethod
    async def generate(self, config: ImageGenConfig) -> ImageGenResult:
        """Generate one image and return its URL once ready."""
