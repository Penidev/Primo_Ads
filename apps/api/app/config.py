"""Application configuration.

Settings are loaded from environment variables (or a local .env file in dev).
Required variables are validated at startup — the app fails fast with a clear
error if any are missing (Requirement 1.5).
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, ValidationError, field_validator
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

    # --- Database topology ---
    # Set when `database_url` points at a transaction-mode pooler: Supabase's
    # Supavisor on port 6543, or PgBouncer in transaction mode. Such a pooler
    # hands each transaction a different backend, so asyncpg's prepared
    # statements get looked up on a connection that never created them.
    db_behind_transaction_pooler: bool = False

    # Session-mode DSN used only by Alembic. A transaction-mode pooler does not
    # support the session-level behaviour migrations rely on, and `CREATE
    # EXTENSION` wants a direct connection. Falls back to `database_url`.
    # On Supabase this is the port 5432 connection string.
    migration_database_url: str | None = None

    # Require TLS to the database. Always on in production regardless of this
    # value; exposed so staging can opt in too.
    db_require_ssl: bool = False

    # --- Auth tuning ---
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # --- App URLs ---
    frontend_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"

    # --- Proxy topology ---
    # How many proxies that append to X-Forwarded-For sit between a browser and
    # this app. Used to locate the real client IP for rate limiting.
    #
    # Default 0 means the header is ignored entirely and the socket peer is used.
    # That is deliberate: X-Forwarded-For is attacker-controlled at its left end,
    # so a wrong value must under-trust rather than over-trust. Set this to the
    # actual hop count for your deployment, and no higher.
    #
    # Primo's browser traffic reaches the API through the Next.js rewrite on
    # Vercel, so count Vercel's edge plus your container host's load balancer.
    trusted_proxy_count: int = Field(default=0, ge=0, le=8)

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

    @field_validator("database_url", "migration_database_url")
    @classmethod
    def _check_postgres_dsn(cls, value: str | None) -> str | None:
        """Catch the two DSN mistakes that produce unhelpful runtime errors.

        Supabase (and most dashboards) hand out a `postgresql://...?sslmode=require`
        string. Pasted verbatim that fails twice over: SQLAlchemy picks the sync
        psycopg driver, and asyncpg rejects `sslmode` as an unknown keyword. Both
        surface far from the cause, so they are caught here instead.
        """
        if value is None:
            return None
        if "sslmode=" in value:
            raise ValueError(
                "asyncpg does not understand 'sslmode'. Remove it from the DSN and "
                "set DB_REQUIRE_SSL=true instead."
            )
        if value.startswith("postgres://") or value.startswith("postgresql://"):
            raise ValueError(
                "DSN must name the async driver: use 'postgresql+asyncpg://...' "
                "(the connection string copied from a dashboard will not have it)."
            )
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def require_db_ssl(self) -> bool:
        """TLS to the database is non-negotiable in production."""
        return self.db_require_ssl or self.is_production

    @property
    def alembic_database_url(self) -> str:
        """DSN for migrations: the session-mode one when supplied."""
        return self.migration_database_url or self.database_url

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
        raise RuntimeError("PROVIDER_MODE=mock is not permitted when ENVIRONMENT=production.")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings, failing fast with a clear message if invalid."""
    try:
        loaded = Settings()  # type: ignore[call-arg]
        _assert_provider_mode_safe(loaded)
        return loaded
    except ValidationError as exc:
        # Missing and malformed are different operator problems, and a malformed
        # value has a specific reason worth printing. The previous version listed
        # only field names, which threw away the explanation the validators go to
        # the trouble of producing.
        missing: list[str] = []
        invalid: list[str] = []
        for err in exc.errors():
            field = ".".join(str(loc) for loc in err["loc"]) or "(root)"
            if err["type"] == "missing":
                missing.append(field.upper())
            else:
                invalid.append(f"{field.upper()}: {err['msg']}")

        parts: list[str] = []
        if missing:
            parts.append("missing: " + ", ".join(missing))
        if invalid:
            parts.append("invalid: " + "; ".join(invalid))
        detail = " | ".join(parts) if parts else str(exc)
        raise RuntimeError(f"Configuration error. {detail}") from exc


settings = get_settings()
