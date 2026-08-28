"""Provider -> adapter resolution.

Adding a provider means registering one adapter here. Adding a *model* on an
existing provider needs no code change at all — just a `video_models` row.
"""

from app.adapters.video.base import VideoModelAdapter, VideoProviderError
from app.adapters.video.fal_adapter import FalVideoAdapter

_ADAPTERS: dict[str, type[VideoModelAdapter]] = {
    FalVideoAdapter.provider_name: FalVideoAdapter,
}


def available_providers() -> list[str]:
    return sorted(_ADAPTERS)


def get_adapter(provider: str) -> VideoModelAdapter:
    """Instantiate the adapter for `provider`, or raise if unsupported."""
    adapter_cls = _ADAPTERS.get((provider or "").lower())
    if adapter_cls is None:
        raise VideoProviderError(f"No adapter registered for provider '{provider}'.")
    return adapter_cls()


def register_adapter(adapter_cls: type[VideoModelAdapter]) -> None:
    """Register an additional provider adapter (used by tests and plugins)."""
    _ADAPTERS[adapter_cls.provider_name] = adapter_cls
