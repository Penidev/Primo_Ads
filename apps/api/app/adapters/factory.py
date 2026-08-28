"""Provider selection — the single place mock and live implementations diverge.

Everything else in the codebase asks this module for an adapter and receives the
abstract interface. That is what keeps mock mode from becoming a bottleneck:

* No service or route knows whether it holds a mock or a live adapter.
* Adding a real API later means editing one branch here, not hunting call sites.
* `PROVIDER_MODE=live` is the default, and mock mode is rejected in production.

Each getter raises `ProviderUnavailableError` when the live provider is not
configured, so callers surface a single consistent failure regardless of mode.
"""

from app.adapters.image.base import ImageAdapter, ImageProviderError
from app.adapters.llm.base import LLMAdapter
from app.adapters.storage.base import StorageAdapter
from app.adapters.video.base import VideoModelAdapter, VideoProviderError
from app.config import settings


class ProviderUnavailableError(Exception):
    """A required provider is not configured in this environment."""


# ------------------------------------------------------------------ LLM


def get_llm_adapter() -> LLMAdapter:
    if settings.use_mock_providers:
        from app.adapters.mock.mock_llm import MockLLMAdapter

        return MockLLMAdapter()

    from app.adapters.llm.gemini import GeminiAdapter, LLMConfigurationError

    try:
        return GeminiAdapter()
    except LLMConfigurationError as exc:
        raise ProviderUnavailableError(
            "Script generation is not configured on this environment."
        ) from exc


# ---------------------------------------------------------------- images


def get_image_adapter() -> ImageAdapter:
    if settings.use_mock_providers:
        from app.adapters.mock.mock_image import MockImageAdapter

        return MockImageAdapter()

    from app.adapters.image.fal_image_adapter import FalImageAdapter

    try:
        return FalImageAdapter()
    except ImageProviderError as exc:
        raise ProviderUnavailableError(
            "Image generation is not configured on this environment."
        ) from exc


# ----------------------------------------------------------------- video


def get_video_adapter(provider: str) -> VideoModelAdapter:
    """Resolve the adapter for a registry row's `provider` value.

    In mock mode every registered model routes to the mock adapter, so the model
    registry, credit multipliers, and selection UI all still behave normally.
    """
    if settings.use_mock_providers:
        from app.adapters.mock.mock_video import MockVideoAdapter

        return MockVideoAdapter()

    from app.adapters.video.registry import get_adapter

    try:
        return get_adapter(provider)
    except VideoProviderError as exc:
        raise ProviderUnavailableError(str(exc)) from exc


# --------------------------------------------------------------- storage


def get_storage_adapter() -> StorageAdapter:
    if settings.use_mock_providers:
        from app.adapters.storage.local_adapter import LocalStorageAdapter

        return LocalStorageAdapter()

    from app.adapters.storage.s3_adapter import S3StorageAdapter

    try:
        return S3StorageAdapter()
    except RuntimeError as exc:
        raise ProviderUnavailableError("Storage is not configured.") from exc


def get_optional_storage_adapter() -> StorageAdapter | None:
    """Storage where absence is tolerable (e.g. retaining swipe-file sources)."""
    try:
        return get_storage_adapter()
    except ProviderUnavailableError:
        return None
