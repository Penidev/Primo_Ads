"""Async SQLAlchemy engine, session factory, and declarative base."""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


def _connect_args() -> dict[str, Any]:
    args: dict[str, Any] = {}

    if settings.require_db_ssl:
        # asyncpg's own keyword. `sslmode` is libpq's and is rejected here, which
        # is why the config validator refuses a DSN carrying it.
        args["ssl"] = "require"

    if settings.db_behind_transaction_pooler:
        # A transaction-mode pooler gives each transaction a different backend,
        # so a prepared statement created on one is missing on the next. asyncpg
        # prepares everything by default, which surfaces as
        # "prepared statement ... does not exist" under load rather than
        # immediately, so it is disabled outright.
        args["statement_cache_size"] = 0

    return args


def _engine_kwargs() -> dict[str, Any]:
    if settings.db_behind_transaction_pooler:
        # Pooling on top of a pooler holds backends open that the pooler is
        # trying to hand around, and Supabase connection limits are small.
        return {"poolclass": NullPool}
    return {"pool_pre_ping": True, "pool_recycle": 1800}


engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    connect_args=_connect_args(),
    **_engine_kwargs(),
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
