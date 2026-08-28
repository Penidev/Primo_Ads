"""Provider factory tests.

These encode the guarantee that mock mode does not become a bottleneck:

* the factory is the only thing that knows which mode is active,
* `PROVIDER_MODE=live` is the default,
* live mode without credentials fails with one consistent error type, so callers
  need no per-provider special cases,
* mock mode cannot be used in production.
"""

import pytest

from app.adapters.factory import (
    ProviderUnavailableError,
    get_image_adapter,
    get_llm_adapter,
    get_optional_storage_adapter,
    get_storage_adapter,
    get_video_adapter,
)
from app.adapters.image.base import ImageAdapter
from app.adapters.llm.base import LLMAdapter
from app.adapters.storage.base import StorageAdapter
from app.adapters.video.base import VideoModelAdapter
from app.config import Settings, _assert_provider_mode_safe


@pytest.fixture
def mock_mode(monkeypatch, tmp_path):
    from app.config import settings

    monkeypatch.setattr(settings, "provider_mode", "mock", raising=False)
    monkeypatch.setattr(settings, "mock_media_dir", str(tmp_path), raising=False)
    return settings


@pytest.fixture
def live_mode_without_keys(monkeypatch):
    """Live mode with every credential absent."""
    from app.config import settings

    monkeypatch.setattr(settings, "provider_mode", "live", raising=False)
    for field in ("gemini_api_key", "fal_key", "aws_s3_bucket"):
        monkeypatch.setattr(settings, field, None, raising=False)
    return settings


class TestDefaults:
    def test_live_is_the_default_mode(self):
        """Nobody should get fakes by forgetting to set a variable."""
        assert Settings.model_fields["provider_mode"].default == "live"


class TestMockMode:
    def test_returns_llm_conforming_to_interface(self, mock_mode):
        assert isinstance(get_llm_adapter(), LLMAdapter)

    def test_returns_image_conforming_to_interface(self, mock_mode):
        assert isinstance(get_image_adapter(), ImageAdapter)

    def test_returns_storage_conforming_to_interface(self, mock_mode):
        assert isinstance(get_storage_adapter(), StorageAdapter)

    @pytest.mark.parametrize("provider", ["fal", "runway", "anything-at-all"])
    def test_every_registry_provider_routes_to_the_mock(self, mock_mode, provider):
        """The model registry keeps working; only the transport is faked."""
        assert isinstance(get_video_adapter(provider), VideoModelAdapter)

    def test_needs_no_credentials(self, mock_mode, monkeypatch):
        for field in ("gemini_api_key", "fal_key", "aws_s3_bucket"):
            monkeypatch.setattr(mock_mode, field, None, raising=False)
        assert get_llm_adapter() is not None
        assert get_image_adapter() is not None
        assert get_storage_adapter() is not None


class TestLiveModeWithoutCredentials:
    """One error type across providers, so callers need no special cases."""

    def test_llm_raises_provider_unavailable(self, live_mode_without_keys):
        with pytest.raises(ProviderUnavailableError):
            get_llm_adapter()

    def test_image_raises_provider_unavailable(self, live_mode_without_keys):
        with pytest.raises(ProviderUnavailableError):
            get_image_adapter()

    def test_storage_raises_provider_unavailable(self, live_mode_without_keys):
        with pytest.raises(ProviderUnavailableError):
            get_storage_adapter()

    def test_unknown_video_provider_raises_provider_unavailable(
        self, live_mode_without_keys
    ):
        with pytest.raises(ProviderUnavailableError):
            get_video_adapter("no-such-provider")

    def test_optional_storage_returns_none_instead_of_raising(
        self, live_mode_without_keys
    ):
        assert get_optional_storage_adapter() is None


class TestProductionSafety:
    def test_mock_mode_is_refused_in_production(self):
        """Serving fabricated creative work to customers must be impossible."""
        settings = Settings(
            database_url="postgresql+asyncpg://u:p@localhost/db",
            redis_url="redis://localhost:6379/0",
            jwt_secret="a-sufficiently-long-secret",
            environment="production",
            provider_mode="mock",
        )
        with pytest.raises(RuntimeError, match="not permitted"):
            _assert_provider_mode_safe(settings)

    def test_live_mode_is_allowed_in_production(self):
        settings = Settings(
            database_url="postgresql+asyncpg://u:p@localhost/db",
            redis_url="redis://localhost:6379/0",
            jwt_secret="a-sufficiently-long-secret",
            environment="production",
            provider_mode="live",
        )
        _assert_provider_mode_safe(settings)  # must not raise

    def test_mock_mode_is_allowed_outside_production(self):
        settings = Settings(
            database_url="postgresql+asyncpg://u:p@localhost/db",
            redis_url="redis://localhost:6379/0",
            jwt_secret="a-sufficiently-long-secret",
            environment="development",
            provider_mode="mock",
        )
        _assert_provider_mode_safe(settings)  # must not raise
