"""Authentication endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas.auth import (
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)
from app.services import analytics_service as analytics
from app.services.audit_service import (
    ACTION_ADMIN_LOGIN,
    AuditService,
    request_context,
)
from app.services.auth_service import AuthError, AuthService
from app.services.mfa_service import MfaService
from app.services.monitoring_service import (
    EVENT_LOGIN_FAILED,
    EVENT_MFA_FAILED,
    EVENT_PASSWORD_RESET_COMPLETED,
    EVENT_PASSWORD_RESET_REQUESTED,
    SEVERITY_WARNING,
    MonitoringService,
)
from app.services.password_reset_service import (
    PasswordResetError,
    PasswordResetService,
)
from app.utils.rate_limit import AUTH_LIMIT, PASSWORD_RESET_LIMIT, rate_limited

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
ACCESS_COOKIE = "access_token"


def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    secure = settings.is_production
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        httponly=True,
        secure=secure,
        samesite="strict",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        httponly=True,
        secure=secure,
        samesite="strict",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/",
    )


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limited(AUTH_LIMIT))],
)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> User:
    service = AuthService(db)
    try:
        user = await service.register(body.email, body.password, body.full_name)
    except AuthError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    await analytics.capture(analytics.EVENT_USER_REGISTERED, distinct_id=str(user.id))
    return user


@router.post("/login", dependencies=[Depends(rate_limited(AUTH_LIMIT))])
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate, enforcing the account's MFA policy.

    Returns a 401 with `mfa_required` when a second factor is needed, and a 403
    with `mfa_enrolment_required` when an admin has not enrolled yet.
    """
    service = AuthService(db)
    monitoring = MonitoringService(db)
    context = request_context(request)

    try:
        user = await service.authenticate(body.email, body.password)
    except AuthError as exc:
        await monitoring.record_event(
            EVENT_LOGIN_FAILED,
            severity=SEVERITY_WARNING,
            ip_address=context["ip_address"],
            description="Failed login attempt",
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    mfa = MfaService(db)

    # Admins without a second factor cannot proceed to a session.
    if MfaService.is_required(user) and not user.mfa_enabled:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Admin accounts must set up two-factor authentication before signing in.",
        )

    if user.mfa_enabled:
        if not body.mfa_code:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Enter the code from your authenticator app.",
                headers={"X-MFA-Required": "true"},
            )
        if not await mfa.verify_challenge(user, body.mfa_code):
            await monitoring.record_event(
                EVENT_MFA_FAILED,
                severity=SEVERITY_WARNING,
                user_id=user.id,
                ip_address=context["ip_address"],
                description="Failed MFA challenge",
            )
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "That code is not valid.")

    access, refresh = await service.issue_tokens(user)
    _set_auth_cookies(response, access, refresh)

    if user.is_admin:
        await AuditService(db).record(
            ACTION_ADMIN_LOGIN, actor=user, request=request
        )

    return TokenResponse(access_token=access)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limited(AUTH_LIMIT))],
)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No refresh token")
    service = AuthService(db)
    try:
        access, new_refresh = await service.rotate_refresh(token)
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    _set_auth_cookies(response, access, new_refresh)
    return TokenResponse(access_token=access)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> None:
    token = request.cookies.get(REFRESH_COOKIE)
    if token:
        await AuthService(db).revoke_family(token)
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")


@router.get("/me", response_model=UserPublic)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post(
    "/password-reset",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limited(PASSWORD_RESET_LIMIT))],
)
async def request_password_reset(
    body: PasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Begin a password reset.

    Always returns the same response whether or not the address exists, so this
    endpoint cannot be used to enumerate accounts (SECURITY.md §1).
    """
    token = await PasswordResetService(db).request_reset(body.email)

    if token:
        context = request_context(request)
        await MonitoringService(db).record_event(
            EVENT_PASSWORD_RESET_REQUESTED,
            user_id=None,
            ip_address=context["ip_address"],
            description="Password reset requested",
        )
        # TODO(email): deliver the link once an email transport is configured.
        # Logged at debug level only, and never returned in the response.
        logger.debug("Password reset token issued (length %d)", len(token))

    return {
        "detail": "If an account exists for that address, a reset link has been sent."
    }


@router.post(
    "/password-reset/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limited(PASSWORD_RESET_LIMIT))],
)
async def confirm_password_reset(
    body: PasswordResetConfirm,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Consume a reset token and set a new password.

    Succeeding also revokes every existing session for the account.
    """
    try:
        user = await PasswordResetService(db).confirm_reset(
            body.token, body.new_password
        )
    except PasswordResetError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    context = request_context(request)
    await MonitoringService(db).record_event(
        EVENT_PASSWORD_RESET_COMPLETED,
        severity=SEVERITY_WARNING,
        user_id=user.id,
        ip_address=context["ip_address"],
        description="Password reset completed; sessions revoked",
    )
