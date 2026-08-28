"""Test fixtures.

Database-backed tests run against the project's Postgres instance (the schema
uses Postgres-specific types — UUID, JSONB, ARRAY, pgvector — so SQLite is not a
viable substitute). Run them inside the dev stack:

    make test-api

Tests that need the database request the `db` fixture; pure-logic tests do not
and run anywhere.
"""

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.session import Base


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """A session bound to a transaction that is rolled back after each test."""
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    connection = await engine.connect()
    transaction = await connection.begin()
    session_factory = async_sessionmaker(bind=connection, expire_on_commit=False)
    session = session_factory()

    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()
        await engine.dispose()


@pytest_asyncio.fixture
async def seeded_user(db: AsyncSession):
    """Create a user with a wallet for credit tests."""
    from app.models import User, Wallet

    user = User(email=f"test-{uuid.uuid4().hex[:8]}@example.com", is_active=True)
    db.add(user)
    await db.flush()
    db.add(Wallet(user_id=user.id, balance_credits=0))
    await db.flush()
    return user
