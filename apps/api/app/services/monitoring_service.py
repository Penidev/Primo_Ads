"""Error monitoring, structured logging, and security alerting.

Design notes:
* Sentry is optional. If the SDK or DSN is absent, every function here degrades
  to structured logging rather than failing — monitoring must never be the reason
  a request breaks.
* Events are scrubbed before they leave the process: emails, tokens, API keys,
  card-like numbers, and known secret field names are redacted (SECURITY.md §10).
* Alert thresholds are evaluated against `security_events`, so anomalies are
  detected from recorded facts rather than in-memory counters that reset.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import CreditTransaction, SecurityEvent
from app.utils.scrubbing import scrub, scrub_text

logger = logging.getLogger("primo")

# ---------------------------------------------------------------- event names

EVENT_LOGIN_FAILED = "auth.login_failed"
EVENT_MFA_FAILED = "auth.mfa_failed"
EVENT_WEBHOOK_FORGERY = "payment.webhook_signature_failed"
EVENT_RATE_LIMIT_TRIPPED = "abuse.rate_limit_tripped"
EVENT_UNUSUAL_SPEND = "abuse.unusual_spend"
EVENT_ADMIN_ACTION = "admin.sensitive_action"
EVENT_PROVIDER_FAILURE = "provider.failure"
# noqa on both: these are event-name constants, not credentials. S105 keys off the
# word "PASSWORD" in the identifier.
EVENT_PASSWORD_RESET_REQUESTED = "auth.password_reset_requested"  # noqa: S105
EVENT_PASSWORD_RESET_COMPLETED = "auth.password_reset_completed"  # noqa: S105

SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_CRITICAL = "critical"

# ------------------------------------------------------------ alert thresholds

# Failed logins from one identity within the window before we flag it.
FAILED_LOGIN_THRESHOLD = 10
FAILED_LOGIN_WINDOW_MINUTES = 15

# Any webhook signature failure is worth knowing about immediately.
WEBHOOK_FORGERY_THRESHOLD = 1
WEBHOOK_FORGERY_WINDOW_MINUTES = 60

# Credits spent by one user in an hour before we consider it anomalous.
UNUSUAL_SPEND_CREDITS = 500
UNUSUAL_SPEND_WINDOW_MINUTES = 60

# ------------------------------------------------------------------- Sentry

_sentry_ready = False


def init_monitoring() -> bool:
    """Initialise Sentry if it is installed and configured. Safe to call once."""
    global _sentry_ready
    if _sentry_ready:
        return True

    dsn = settings.sentry_dsn
    if not dsn:
        logger.info("Sentry DSN not configured; using structured logging only.")
        return False

    try:
        import sentry_sdk
    except ImportError:
        logger.warning("sentry-sdk is not installed; using structured logging only.")
        return False

    def _before_send(event: dict, _hint: dict) -> dict:
        # Final safety net: scrub whatever the SDK collected.
        return scrub(event)

    sentry_sdk.init(
        dsn=dsn,
        environment=settings.environment,
        # PII is never sent, regardless of SDK defaults.
        send_default_pii=False,
        traces_sample_rate=0.1 if settings.is_production else 0.0,
        before_send=_before_send,
    )
    _sentry_ready = True
    logger.info("Sentry monitoring initialised.")
    return True


def capture_exception(exc: BaseException, **extra: Any) -> None:
    """Report an exception to Sentry when available; always log it."""
    safe_extra = scrub(extra) if extra else {}
    logger.exception("Unhandled error: %s", scrub_text(str(exc)), extra=safe_extra)
    if not _sentry_ready:
        return
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            for key, value in safe_extra.items():
                scope.set_extra(key, value)
            sentry_sdk.capture_exception(exc)
    except Exception:  # noqa: BLE001 - monitoring must never raise
        logger.warning("Failed to forward exception to Sentry.")


def capture_message(message: str, level: str = "info", extra: dict | None = None) -> None:
    """Report a message to Sentry when available; always log it."""
    safe_extra = scrub(extra or {})
    logger.log(
        getattr(logging, level.upper(), logging.INFO),
        scrub_text(message),
        extra=safe_extra,
    )
    if not _sentry_ready:
        return
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            for key, value in safe_extra.items():
                scope.set_extra(key, value)
            sentry_sdk.capture_message(scrub_text(message), level=level)
    except Exception:  # noqa: BLE001 - monitoring must never raise
        logger.warning("Failed to forward message to Sentry.")


# ------------------------------------------------------- security event store


class MonitoringService:
    """Records security events and evaluates alert conditions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_event(
        self,
        event_type: str,
        *,
        severity: str = SEVERITY_INFO,
        user_id: Any = None,
        ip_address: str | None = None,
        description: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        """Persist a security signal. Never raises."""
        try:
            self.db.add(
                SecurityEvent(
                    event_type=event_type,
                    severity=severity,
                    user_id=user_id,
                    ip_address=ip_address,
                    description=scrub_text(description) if description else None,
                    detail=scrub(detail) if detail else None,
                )
            )
            await self.db.commit()
        except Exception:  # noqa: BLE001 - telemetry must not break the request
            await self.db.rollback()
            logger.warning("Failed to record security event %s", event_type)
            return

        if severity in (SEVERITY_WARNING, SEVERITY_CRITICAL):
            capture_message(
                f"Security event: {event_type}",
                level="warning" if severity == SEVERITY_WARNING else "error",
                extra={"description": description, **(detail or {})},
            )

    async def _count_since(self, event_type: str, minutes: int) -> int:
        since = datetime.now(UTC) - timedelta(minutes=minutes)
        return (
            await self.db.scalar(
                select(func.count())
                .select_from(SecurityEvent)
                .where(
                    SecurityEvent.event_type == event_type,
                    SecurityEvent.created_at >= since,
                )
            )
            or 0
        )

    async def spend_in_window(self, user_id: Any, minutes: int) -> float:
        """Credits debited for a user within the window (positive number)."""
        since = datetime.now(UTC) - timedelta(minutes=minutes)
        total = await self.db.scalar(
            select(func.coalesce(func.sum(CreditTransaction.amount), 0)).where(
                CreditTransaction.user_id == user_id,
                CreditTransaction.amount < 0,
                CreditTransaction.created_at >= since,
            )
        )
        return abs(float(total or 0))

    async def check_unusual_spend(self, user_id: Any) -> bool:
        """Flag a user whose spend in the last hour looks anomalous."""
        spent = await self.spend_in_window(user_id, UNUSUAL_SPEND_WINDOW_MINUTES)
        if spent < UNUSUAL_SPEND_CREDITS:
            return False
        await self.record_event(
            EVENT_UNUSUAL_SPEND,
            severity=SEVERITY_WARNING,
            user_id=user_id,
            description=(f"{spent:.0f} credits spent in {UNUSUAL_SPEND_WINDOW_MINUTES} minutes"),
            detail={"credits_spent": spent},
        )
        return True

    async def active_alerts(self) -> list[dict[str, Any]]:
        """Current breaches of the alert thresholds, for the admin dashboard."""
        checks = [
            (
                EVENT_LOGIN_FAILED,
                FAILED_LOGIN_THRESHOLD,
                FAILED_LOGIN_WINDOW_MINUTES,
                "Elevated failed logins",
            ),
            (
                EVENT_WEBHOOK_FORGERY,
                WEBHOOK_FORGERY_THRESHOLD,
                WEBHOOK_FORGERY_WINDOW_MINUTES,
                "Webhook signature verification failed",
            ),
        ]
        alerts: list[dict[str, Any]] = []
        for event_type, threshold, window, label in checks:
            count = await self._count_since(event_type, window)
            if count >= threshold:
                alerts.append(
                    {
                        "event_type": event_type,
                        "label": label,
                        "count": count,
                        "threshold": threshold,
                        "window_minutes": window,
                    }
                )
        return alerts

    async def recent_events(self, limit: int = 100) -> list[SecurityEvent]:
        rows = await self.db.scalars(
            select(SecurityEvent).order_by(SecurityEvent.created_at.desc()).limit(limit)
        )
        return list(rows)
