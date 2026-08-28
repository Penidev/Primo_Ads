"""Shared FastAPI dependencies: DB session, current user, admin guard."""

import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import User
from app.utils.tokens import TokenError, decode_token


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the Bearer access token.

    Accepts the token from the Authorization header (mobile/native clients) or
    an `access_token` cookie (web). Business logic never trusts client-supplied
    identity beyond this verified token.
    """
    token: str | None = None
    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth[7:]
    if token is None:
        token = request.cookies.get("access_token")
    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    try:
        payload = decode_token(token, expected_type="access")
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token subject") from exc

    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """Guard admin-only routes. Admin flag is server-side only (SECURITY.md §2)."""
    if not user.is_admin:
        # 404 rather than 403 to avoid revealing the route exists
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return user
