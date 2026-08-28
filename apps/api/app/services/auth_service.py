"""Authentication business logic: register, login, refresh rotation.

Refresh-token families are tracked in Redis so a used token's jti is recorded;
if an old (already-rotated) refresh token is presented again, we treat it as
theft and revoke the whole family (SECURITY.md §1).
"""

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import User, Wallet
from app.utils.security import hash_password, validate_password_strength, verify_password
from app.utils.tokens import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)


class AuthError(Exception):
    """Domain error for auth failures (mapped to HTTP by the route)."""


def _redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url)


def _family_key(fam: str) -> str:
    return f"refresh:family:{fam}"


def _user_families_key(user_id: str) -> str:
    """Index of a user's active refresh families.

    Needed so every session for one account can be revoked at once — on password
    reset, for example. Without this index the family keys are only reachable by
    family id, which nothing else knows.
    """
    return f"refresh:user:{user_id}"


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, email: str, password: str, full_name: str | None) -> User:
        pw_errors = validate_password_strength(password)
        if pw_errors:
            raise AuthError(" ".join(pw_errors))

        existing = await self.db.scalar(select(User).where(User.email == email))
        if existing:
            # Do not reveal whether the email exists; the route returns a
            # generic success/duplicate handling per SECURITY.md.
            raise AuthError("An account with that email already exists.")

        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            is_active=True,
        )
        self.db.add(user)
        await self.db.flush()
        self.db.add(Wallet(user_id=user.id, balance_credits=0))
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def authenticate(self, email: str, password: str) -> User:
        user = await self.db.scalar(select(User).where(User.email == email))
        # Constant-ish work whether or not the user exists: verify against a
        # dummy hash when missing to reduce timing signal.
        if user is None or not user.password_hash:
            hash_password("dummy-timing-equalizer")
            raise AuthError("Invalid email or password.")
        if not verify_password(password, user.password_hash):
            raise AuthError("Invalid email or password.")
        if not user.is_active:
            raise AuthError("Account is disabled.")
        return user

    async def issue_tokens(self, user: User) -> tuple[str, str]:
        """Create a fresh access + refresh token pair and register the family."""
        access = create_access_token(str(user.id), extra={"admin": user.is_admin})
        refresh, fam, jti = create_refresh_token(str(user.id))
        ttl = settings.refresh_token_expire_days * 86400
        client = _redis()
        try:
            # Current valid jti for this family.
            await client.set(_family_key(fam), jti, ex=ttl)
            # Index the family against the user so all sessions can be revoked.
            await client.sadd(_user_families_key(str(user.id)), fam)
            await client.expire(_user_families_key(str(user.id)), ttl)
        finally:
            await client.aclose()
        return access, refresh

    async def rotate_refresh(self, refresh_token: str) -> tuple[str, str]:
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except TokenError as exc:
            raise AuthError("Invalid refresh token.") from exc

        fam = payload.get("fam")
        jti = payload.get("jti")
        sub = payload.get("sub")
        if not (fam and jti and sub):
            raise AuthError("Malformed refresh token.")

        client = _redis()
        try:
            current = await client.get(_family_key(fam))
            current = current.decode() if current else None
            if current is None:
                raise AuthError("Refresh token expired or revoked.")
            if current != jti:
                # Reuse of an old token → likely theft. Revoke the family.
                await client.delete(_family_key(fam))
                raise AuthError("Refresh token reuse detected; session revoked.")

            # Rotate: issue a new jti within the same family.
            new_access = create_access_token(sub)
            new_refresh, _, new_jti = create_refresh_token(sub, family_id=fam)
            await client.set(
                _family_key(fam),
                new_jti,
                ex=settings.refresh_token_expire_days * 86400,
            )
            return new_access, new_refresh
        finally:
            await client.aclose()

    async def revoke_family(self, refresh_token: str) -> None:
        """Logout: drop the refresh family so it can no longer rotate."""
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except TokenError:
            return
        fam = payload.get("fam")
        sub = payload.get("sub")
        if not fam:
            return
        client = _redis()
        try:
            await client.delete(_family_key(fam))
            if sub:
                await client.srem(_user_families_key(str(sub)), fam)
        finally:
            await client.aclose()

    @staticmethod
    async def revoke_all_sessions(user_id: str) -> int:
        """Invalidate every refresh family for one account.

        Used after a password reset, where leaving old sessions alive would
        defeat the purpose. Returns the number of families dropped.
        """
        client = _redis()
        try:
            index = _user_families_key(str(user_id))
            families = await client.smembers(index)
            for raw in families:
                fam = raw.decode() if isinstance(raw, bytes) else raw
                await client.delete(_family_key(fam))
            await client.delete(index)
            return len(families)
        except Exception:  # noqa: BLE001 - best effort; the password already changed
            return 0
        finally:
            await client.aclose()
