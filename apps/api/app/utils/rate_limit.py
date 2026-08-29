"""Redis-backed sliding-window rate limiting (SECURITY.md §6).

Limits are applied per identity (authenticated user id when available, otherwise
client IP). Expensive endpoints get their own tighter buckets so a single user
cannot exhaust provider budget or brute-force credentials.

Fails open on Redis errors: availability of the product is preferred over hard
denial, and the ledger/auth layers remain the authoritative protections.
"""

import ipaddress
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


def _socket_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def resolve_client_ip(request: Request) -> str:
    """Resolve the client IP against the configured trusted-proxy depth.

    X-Forwarded-For is built by *appending*: each proxy adds the peer it received
    from. So the left-most entry is whatever the caller sent, and is entirely
    attacker-controlled. Reading it — which this function used to do — lets a
    caller present a fresh fake address on every request and bypass IP rate
    limiting completely, which matters most on the endpoints that have no user
    id to bucket by yet: login, registration, and password reset.

    The real client is therefore counted from the right, skipping exactly the
    proxies we operate:

        client sends nothing   ->  "C, P1"              depth 2 -> C
        client forges an entry ->  "9.9.9.9, C, P1"     depth 2 -> C

    A chain shorter than the configured depth means the request did not traverse
    the expected proxies, so nothing in the header is trustworthy and the socket
    peer is used instead. Same when the value is not a valid IP, which also stops
    a malformed header from being written into a Redis key.
    """
    depth = settings.trusted_proxy_count
    if depth <= 0:
        return _socket_ip(request)

    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return _socket_ip(request)

    chain = [part.strip() for part in forwarded.split(",") if part.strip()]
    if len(chain) < depth:
        return _socket_ip(request)

    candidate = chain[len(chain) - depth]
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return _socket_ip(request)
    return candidate


def _identity(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    return f"user:{user_id}" if user_id else f"ip:{resolve_client_ip(request)}"


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
