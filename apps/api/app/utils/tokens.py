"""JWT access/refresh token creation and verification (SECURITY.md §1).

Access tokens are short-lived; refresh tokens are longer-lived and rotated on
use. Refresh tokens carry a family id + jti so reuse can be detected and the
whole family revoked (theft mitigation).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from jose import JWTError, jwt

from app.config import settings

TokenType = Literal["access", "refresh"]


class TokenError(Exception):
    """Raised when a token is invalid, expired, or the wrong type."""


def _now() -> datetime:
    return datetime.now(UTC)


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    expire = _now() + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": "access",
        "iat": _now(),
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    subject: str,
    family_id: str | None = None,
    jti: str | None = None,
) -> tuple[str, str, str]:
    """Return (token, family_id, jti). Reuse the family_id across rotations."""
    fam = family_id or str(uuid.uuid4())
    token_jti = jti or str(uuid.uuid4())
    expire = _now() + timedelta(days=settings.refresh_token_expire_days)
    payload = {
        "sub": subject,
        "type": "refresh",
        "iat": _now(),
        "exp": expire,
        "fam": fam,
        "jti": token_jti,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, fam, token_jti


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise TokenError("Invalid or expired token") from exc

    if payload.get("type") != expected_type:
        raise TokenError(f"Expected {expected_type} token")
    return payload
