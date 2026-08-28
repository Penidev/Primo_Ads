"""MFA enrolment and terms-of-service acceptance endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas.mfa import (
    MfaActivateRequest,
    MfaActivateResponse,
    MfaDisableRequest,
    MfaSetupResponse,
    MfaStatusResponse,
    TosAcceptRequest,
)
from app.services.audit_service import (
    ACTION_MFA_DISABLED,
    ACTION_MFA_ENABLED,
    AuditService,
)
from app.services.mfa_service import MfaError, MfaService
from app.utils.rate_limit import AUTH_LIMIT, rate_limited

router = APIRouter(prefix="/mfa", tags=["mfa"])


@router.get("", response_model=MfaStatusResponse)
async def mfa_status(user: User = Depends(get_current_user)) -> MfaStatusResponse:
    return MfaStatusResponse(
        mfa_enabled=bool(user.mfa_enabled),
        mfa_required=MfaService.is_required(user),
        recovery_codes_remaining=MfaService.recovery_codes_remaining(user),
    )


@router.post(
    "/setup",
    response_model=MfaSetupResponse,
    dependencies=[Depends(rate_limited(AUTH_LIMIT))],
)
async def begin_setup(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MfaSetupResponse:
    """Issue a secret and QR URI. Enrolment completes only after confirmation."""
    try:
        secret, uri = await MfaService(db).begin_setup(user)
    except MfaError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return MfaSetupResponse(secret=secret, provisioning_uri=uri)


@router.post(
    "/activate",
    response_model=MfaActivateResponse,
    dependencies=[Depends(rate_limited(AUTH_LIMIT))],
)
async def activate(
    body: MfaActivateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MfaActivateResponse:
    """Confirm a live code to switch MFA on. Recovery codes are shown once."""
    try:
        codes = await MfaService(db).activate(user, body.code)
    except MfaError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    await AuditService(db).record(ACTION_MFA_ENABLED, actor=user, request=request)
    return MfaActivateResponse(recovery_codes=codes)


@router.post(
    "/disable",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limited(AUTH_LIMIT))],
)
async def disable(
    body: MfaDisableRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Turn MFA off. Blocked for admins, who must retain a second factor."""
    try:
        await MfaService(db).disable(user, body.password, body.code)
    except MfaError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await AuditService(db).record(ACTION_MFA_DISABLED, actor=user, request=request)


tos_router = APIRouter(prefix="/legal", tags=["legal"])


@tos_router.get("/tos")
async def current_tos(user: User = Depends(get_current_user)) -> dict[str, object]:
    """Current terms version and whether this user has accepted it."""
    return {
        "current_version": settings.tos_version,
        "accepted_version": user.tos_version,
        "accepted_at": user.tos_accepted_at,
        "acceptance_required": user.tos_version != settings.tos_version,
    }


@tos_router.post("/tos/accept")
async def accept_tos(
    body: TosAcceptRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Record acceptance of a specific terms version."""
    if body.version != settings.tos_version:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Terms version mismatch. Current version is {settings.tos_version}.",
        )
    user.tos_version = body.version
    user.tos_accepted_at = datetime.now(UTC)
    await db.commit()
    return {"accepted_version": user.tos_version, "accepted_at": user.tos_accepted_at}
