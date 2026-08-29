"""Audit logging for sensitive actions.

Writes are best-effort by design: an audit failure must never block or roll back
the operation being recorded, but it is surfaced to monitoring so silent loss is
detectable (SECURITY.md §10).
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.models import AuditLog, User

# Canonical action names. Keeping these as constants stops the log filling with
# near-duplicate strings that are then impossible to query.
ACTION_PRICING_RATIO_CHANGED = "pricing.ratio_changed"
ACTION_PRICING_ACTION_CHANGED = "pricing.action_changed"
ACTION_MODEL_CREATED = "model.created"
ACTION_MODEL_UPDATED = "model.updated"
ACTION_PLAN_UPSERTED = "plan.upserted"
ACTION_PACKAGE_UPSERTED = "package.upserted"
ACTION_USER_STATUS_CHANGED = "user.status_changed"
ACTION_CREDITS_GRANTED = "credits.granted"
ACTION_FLAG_TOGGLED = "feature_flag.toggled"
ACTION_BLUEPRINT_APPROVED = "blueprint.approval_changed"
ACTION_BLUEPRINT_DELETED = "blueprint.deleted"
ACTION_MFA_ENABLED = "mfa.enabled"
ACTION_MFA_DISABLED = "mfa.disabled"
ACTION_ADMIN_LOGIN = "admin.login"

MAX_USER_AGENT_CHARS = 500


def request_context(request: Request | None) -> dict[str, str | None]:
    """Extract client attribution from a request, if one is available."""
    if request is None:
        return {"ip_address": None, "user_agent": None}

    forwarded = request.headers.get("x-forwarded-for")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else None)
    )
    agent = request.headers.get("user-agent")
    return {
        "ip_address": ip,
        "user_agent": agent[:MAX_USER_AGENT_CHARS] if agent else None,
    }


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record(
        self,
        action: str,
        *,
        actor: User | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        detail: dict[str, Any] | None = None,
        request: Request | None = None,
    ) -> None:
        """Append an audit entry. Never raises."""
        try:
            context = request_context(request)
            self.db.add(
                AuditLog(
                    actor_id=actor.id if actor else None,
                    actor_email=actor.email if actor else None,
                    action=action,
                    target_type=target_type,
                    target_id=str(target_id) if target_id is not None else None,
                    detail=detail,
                    ip_address=context["ip_address"],
                    user_agent=context["user_agent"],
                )
            )
            await self.db.commit()
        except Exception:  # noqa: BLE001 - auditing must not break the action
            await self.db.rollback()
            from app.services.monitoring_service import capture_message

            capture_message(
                "Audit log write failed",
                level="error",
                extra={"action": action, "target_type": target_type},
            )

    async def list_entries(
        self,
        *,
        action: str | None = None,
        actor_id: uuid.UUID | None = None,
        limit: int = 100,
    ) -> list[AuditLog]:
        stmt = select(AuditLog)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if actor_id:
            stmt = stmt.where(AuditLog.actor_id == actor_id)
        rows = await self.db.scalars(stmt.order_by(AuditLog.created_at.desc()).limit(limit))
        return list(rows)
