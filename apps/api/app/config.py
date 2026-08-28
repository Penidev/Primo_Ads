"""Application configuration.

Settings are loaded from environment variables (or a local .env file in dev).
Required variables are validated at startup — the app fails fast with a clear
error if any are missing (Requirement 1.5).
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Core (required) ---
    environment: Literal["development", "staging", "production"] = "development"
    database_url: str = Field(..., description="PostgreSQL async DSN")
    redis_url: str = Field(..., description="Redis connection URL")
    jwt_secret: str = Field(..., min_length=16, description="Secret for signing JWTs")

    # --- Auth tuning ---
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # --- App URLs ---
    frontend_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"

    # --- AI providers (optional until their phase) ---
    gemini_api_key: str | None = None
    fal_key: str | None = None
    openai_api_key: str | None = None

    # --- Payments (optional until Phase 5) ---
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    paypal_client_id: str | None = None
    paypal_client_secret: str | None = None
    cozzipay_secret_key: str | None = None
    cozzipay_webhook_secret: str | None = None

    # --- Provider mode ---
    # "live" calls real providers; "mock" uses deterministic in-process fakes so
    # the full pipeline runs with no API keys and no cost. Mock mode is refused
    # in production (see _assert_provider_mode_safe below).
    provider_mode: Literal["live", "mock"] = "live"
    # Where mock media is written when using local storage.
    mock_media_dir: str = "/tmp/primo-mock-media"  # noqa: S108 - container-local

    # --- Monitoring (optional; degrades to structured logging) ---
    sentry_dsn: str | None = None
    posthog_api_key: str | None = None
    posthog_host: str = "https://app.posthog.com"

    # --- Legal ---
    tos_version: str = "2026-01"

    # --- Storage (optional until asset/video phases) ---
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_s3_bucket: str | None = None
    aws_region: str = "us-east-1"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def use_mock_providers(self) -> bool:
        return self.provider_mode == "mock"

    @property
    def cors_origins(self) -> list[str]:
        return [self.frontend_url]


def _assert_provider_mode_safe(settings: "Settings") -> None:
    """Refuse to start a production deployment backed by fake providers.

    Mock mode exists for local development and CI. Serving it to real customers
    would silently return fabricated creative work, so this is a hard failure
    rather than a warning.
    """
    if settings.is_production and settings.provider_mode == "mock":
        raise RuntimeError(
            "PROVIDER_MODE=mock is not permitted when ENVIRONMENT=production."
        )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings, failing fast with a clear message if invalid."""
    try:
        loaded = Settings()  # type: ignore[call-arg]
        _assert_provider_mode_safe(loaded)
        return loaded
    except ValidationError as exc:
        missing = [
            ".".join(str(loc) for loc in err["loc"])
            for err in exc.errors()
            if err["type"] in ("missing", "value_error")
        ]
        detail = ", ".join(missing) if missing else str(exc)
        raise RuntimeError(
            f"Invalid or missing configuration. Check these environment variables: {detail}"
        ) from exc


settings = get_settings()
