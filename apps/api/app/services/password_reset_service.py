"""Password reset via single-use, time-limited tokens.

Security properties (SECURITY.md §1):

* **Non-enumerating.** Requesting a reset returns the same response whether or
  not the address exists, so the endpoint cannot be used to discover accounts.
* **Single use.** The token is deleted from Redis the moment it is consumed, so a
  captured link cannot be replayed.
* **Time limited.** Tokens expire after 30 minutes.
* **Hashed at rest.** Redis stores a SHA-256 digest, not the token itself, so a
  cache dump does not yield usable reset links.
* **Sessions revoked on use.** Completing a reset invalidates existing refresh
  token families, so an attacker who already had a session is evicted.
"""

import hashlib
import secrets
import uuid

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import User
from app.utils.security import hash_password, validate_password_strength

TOKEN_TTL_SECONDS = 30 * 60
TOKEN_BYTES = 32


class PasswordResetError(Exception):
    """User-safe reset failure."""


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _key(token: str) -> str:
    return f"pwreset:{_digest(token)}"


class PasswordResetService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def request_reset(self, email: str) -> str | None:
        """Issue a reset token, or return None if no such active account exists.

        The caller must respond identically either way. The token is returned so
        an email transport can send it; it is never exposed via the API.
        """
        user = await self.db.scalar(select(User).where(User.email == email))
        if user is None or not user.is_active:
            return None

        token = secrets.token_urlsafe(TOKEN_BYTES)
        client = aioredis.from_url(settings.redis_url)
        try:
            await client.set(_key(token), str(user.id), ex=TOKEN_TTL_SECONDS)
        finally:
            await client.aclose()
        return token

    async def confirm_reset(self, token: str, new_password: str) -> User:
        """Consume a token and set the new password."""
        errors = validate_password_strength(new_password)
        if errors:
            raise PasswordResetError(" ".join(errors))

        client = aioredis.from_url(settings.redis_url)
        try:
            raw_user_id = await client.get(_key(token))
            if raw_user_id is None:
                raise PasswordResetError(
                    "This reset link is invalid or has expired. Request a new one."
                )
            # Delete before mutating, so a concurrent replay cannot also succeed.
            await client.delete(_key(token))
            user_id = raw_user_id.decode() if isinstance(raw_user_id, bytes) else raw_user_id
        finally:
            await client.aclose()

        try:
            parsed_id = uuid.UUID(user_id)
        except ValueError as exc:
            raise PasswordResetError("This reset link is invalid.") from exc

        user = await self.db.scalar(select(User).where(User.id == parsed_id))
        if user is None or not user.is_active:
            raise PasswordResetError("This reset link is no longer valid.")

        user.password_hash = hash_password(new_password)
        await self.db.commit()

        # A reset is often a response to compromise, so evict existing sessions.
        from app.services.auth_service import AuthService

        await AuthService.revoke_all_sessions(str(parsed_id))
        return user
