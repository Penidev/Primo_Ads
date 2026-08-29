"""Database DSN validation.

Every one of these is a string a dashboard actually hands you. Each used to fail
somewhere far from its cause — a sync-driver import error, or asyncpg rejecting an
unknown keyword mid-connection — so they are rejected at startup with the reason
attached instead.
"""

import pytest
from pydantic import ValidationError

from app.config import Settings

VALID = "postgresql+asyncpg://user:pw@host:5432/db"
BASE = {
    "database_url": VALID,
    "redis_url": "redis://localhost:6379/0",
    "jwt_secret": "x" * 32,
}


def build(**overrides) -> Settings:
    return Settings(**{**BASE, **overrides})  # type: ignore[arg-type]


class TestAcceptedForms:
    def test_async_dsn_is_accepted(self):
        assert build().database_url == VALID

    def test_migration_dsn_may_be_omitted(self):
        assert build().migration_database_url is None

    def test_migration_dsn_falls_back_to_the_runtime_dsn(self):
        assert build().alembic_database_url == VALID

    def test_migration_dsn_is_used_when_supplied(self):
        session_mode = "postgresql+asyncpg://user:pw@host:5432/db"
        settings = build(migration_database_url=session_mode)
        assert settings.alembic_database_url == session_mode


class TestRejectedForms:
    @pytest.mark.parametrize(
        "dsn",
        [
            # Copied straight from a Supabase / Neon / Render dashboard.
            "postgresql://user:pw@host:5432/db",
            "postgres://user:pw@host:5432/db",
        ],
    )
    def test_sync_driver_dsn_is_rejected(self, dsn):
        with pytest.raises(ValidationError, match="asyncpg"):
            build(database_url=dsn)

    def test_sslmode_is_rejected_with_the_alternative_named(self):
        dsn = "postgresql+asyncpg://user:pw@host:5432/db?sslmode=require"
        with pytest.raises(ValidationError, match="DB_REQUIRE_SSL"):
            build(database_url=dsn)

    def test_migration_dsn_is_validated_too(self):
        with pytest.raises(ValidationError, match="asyncpg"):
            build(migration_database_url="postgresql://user:pw@host:5432/db")


class TestSslPolicy:
    def test_ssl_is_off_by_default_in_development(self):
        assert build().require_db_ssl is False

    def test_ssl_can_be_opted_into(self):
        assert build(db_require_ssl=True).require_db_ssl is True

    def test_production_requires_ssl_regardless_of_the_flag(self):
        """Not overridable: an unencrypted production database link is not a
        preference."""
        settings = build(environment="production", db_require_ssl=False)
        assert settings.require_db_ssl is True


class TestProxyDepth:
    def test_defaults_to_trusting_nothing(self):
        assert build().trusted_proxy_count == 0

    @pytest.mark.parametrize("depth", [-1, 9])
    def test_out_of_range_depth_is_rejected(self, depth):
        with pytest.raises(ValidationError):
            build(trusted_proxy_count=depth)
