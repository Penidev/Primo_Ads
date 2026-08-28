"""Product analytics via PostHog's capture API.

Three rules this module holds to:

1. **Never block or break a request.** Events are fire-and-forget; any failure is
   swallowed and logged. Analytics is not worth a 500.
2. **No PII leaves the process.** `distinct_id` is the user's UUID, never their
   email, and every property payload is scrubbed (SECURITY.md §10).
3. **Optional.** With no API key configured, every call is a no-op, so local and
   test environments need no analytics account.

Uses the HTTP endpoint directly instead of the SDK to avoid a dependency and to
keep the failure behaviour explicit.
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import settings
from app.utils.scrubbing import scrub

logger = logging.getLogger("primo.analytics")

CAPTURE_TIMEOUT = httpx.Timeout(5.0, connect=2.0)

# --- funnel events -----------------------------------------------------------
EVENT_USER_REGISTERED = "user_registered"
EVENT_ONBOARDING_COMPLETED = "onboarding_completed"
EVENT_PROJECT_CREATED = "project_created"
EVENT_BRIEF_COMPLETED = "brief_completed"
EVENT_SCRIPT_GENERATED = "script_generated"
EVENT_ASSETS_GENERATED = "assets_generated"
EVENT_VIDEO_GENERATION_STARTED = "video_generation_started"
EVENT_VIDEO_COMPLETED = "video_completed"
EVENT_SCENE_REROLLED = "scene_rerolled"
EVENT_PROJECT_EXPORTED = "project_exported"

# --- commercial events -------------------------------------------------------
EVENT_CHECKOUT_STARTED = "checkout_started"
EVENT_CREDITS_PURCHASED = "credits_purchased"
EVENT_INSUFFICIENT_CREDITS = "insufficient_credits"

# --- quality signals ---------------------------------------------------------
EVENT_GENERATION_FAILED = "generation_failed"
EVENT_CONTENT_REFUSED = "content_refused"


def is_enabled() -> bool:
    return bool(settings.posthog_api_key)


async def _send(payload: dict[str, Any]) -> None:
    try:
        async with httpx.AsyncClient(timeout=CAPTURE_TIMEOUT) as client:
            await client.post(f"{settings.posthog_host.rstrip('/')}/capture/", json=payload)
    except Exception:  # noqa: BLE001 - analytics must never surface an error
        logger.debug("Analytics event delivery failed", exc_info=True)


async def capture(
    event: str,
    *,
    distinct_id: str,
    properties: dict[str, Any] | None = None,
) -> None:
    """Record a product event. Returns immediately; delivery happens in the background."""
    if not is_enabled():
        return

    payload = {
        "api_key": settings.posthog_api_key,
        "event": event,
        "distinct_id": str(distinct_id),
        "timestamp": datetime.now(UTC).isoformat(),
        "properties": {
            **(scrub(properties or {})),
            "environment": settings.environment,
            "$lib": "primo-backend",
        },
    }

    # Detach delivery so a slow analytics endpoint cannot slow a user request.
    try:
        task = asyncio.create_task(_send(payload))
        # Keep a reference so the task is not garbage-collected mid-flight.
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    except RuntimeError:
        # No running loop (e.g. called from sync context): skip rather than fail.
        logger.debug("No event loop available for analytics event %s", event)


_background_tasks: set[asyncio.Task] = set()


async def identify(
    distinct_id: str,
    *,
    traits: dict[str, Any] | None = None,
) -> None:
    """Attach non-identifying traits (country, industry, role) to a user.

    Deliberately excludes email and name: cohort analysis needs segments, not
    identities.
    """
    if not is_enabled():
        return
    await capture(
        "$identify",
        distinct_id=distinct_id,
        properties={"$set": scrub(traits or {})},
    )
