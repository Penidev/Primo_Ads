"""Health-check endpoint reporting service connectivity (Requirement 1.2)."""

import redis.asyncio as aioredis
from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings
from app.db.session import engine

router = APIRouter(tags=["health"])


async def _check_database() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _check_redis() -> bool:
    client = aioredis.from_url(settings.redis_url)
    try:
        return bool(await client.ping())
    except Exception:
        return False
    finally:
        await client.aclose()


@router.get("/health")
async def health() -> dict:
    """Report overall status plus each dependency's connectivity."""
    db_ok = await _check_database()
    redis_ok = await _check_redis()
    overall = "ok" if (db_ok and redis_ok) else "degraded"
    return {
        "status": overall,
        "environment": settings.environment,
        "services": {
            "database": "up" if db_ok else "down",
            "redis": "up" if redis_ok else "down",
        },
    }
