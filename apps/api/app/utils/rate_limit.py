"""Redis-backed sliding-window rate limiting (SECURITY.md §6).

Limits are applied per identity (authenticated user id when available, otherwise
client IP). Expensive endpoints get their own tighter buckets so a single user
cannot exhaust provider budget or brute-force credentials.

Fails open on Redis errors: availability of the product is preferred over hard
denial, and the ledger/auth layers remain the authoritative protections.
"""

import time
from dataclasses import dataclass

import redis.asyncio as aioredis
from fastapi import HTTPException, Request, status

from app.config import settings


@dataclass(frozen=True)
class RateLimit:
    requests: int
    window_seconds: int
    bucket: str


# Named buckets used across the API.
AUTH_LIMIT = RateLimit(requests=5, window_seconds=60, bucket="auth")
GENERATION_LIMIT = RateLimit(requests=10, window_seconds=60, bucket="generation")
DEFAULT_LIMIT = RateLimit(requests=100, window_seconds=60, bucket="default")
UPLOAD_LIMIT = RateLimit(requests=20, window_seconds=60, bucket="upload")
CHECKOUT_LIMIT = RateLimit(requests=10, window_seconds=300, bucket="checkout")
# Deliberately strict: reset requests trigger email and are an enumeration and
# mail-flooding vector, so an hour-long window is appropriate.
PASSWORD_RESET_LIMIT = RateLimit(requests=3, window_seconds=3600, bucket="password_reset")


def _client_ip(request: Request) -> str:
    """Best-effort client IP.

    Only the left-most X-Forwarded-For entry is considered, and only because the
    app is expected to sit behind a trusted proxy that sets it. Falls back to the
    socket address.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


def _identity(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    return f"user:{user_id}" if user_id else f"ip:{_client_ip(request)}"


async def enforce(request: Request, limit: RateLimit) -> None:
    """Raise HTTP 429 when the caller exceeds `limit`."""
    key = f"ratelimit:{limit.bucket}:{_identity(request)}"
    client = aioredis.from_url(settings.redis_url)
    try:
        window_start = int(time.time()) // limit.window_seconds
        window_key = f"{key}:{window_start}"
        count = await client.incr(window_key)
        if count == 1:
            await client.expire(window_key, limit.window_seconds * 2)
        if count > limit.requests:
            retry_after = limit.window_seconds - (int(time.time()) % limit.window_seconds)
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many requests. Please slow down.",
                headers={"Retry-After": str(max(retry_after, 1))},
            )
    except HTTPException:
        raise
    except Exception:
        # Redis unavailable: do not block legitimate traffic.
        return
    finally:
        await client.aclose()


def rate_limited(limit: RateLimit):
    """FastAPI dependency factory: `Depends(rate_limited(AUTH_LIMIT))`."""

    async def dependency(request: Request) -> None:
        await enforce(request, limit)

    return dependency
