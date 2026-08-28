"""Multi-factor authentication.

Policy (Requirement 2.6): MFA is optional for regular users and **required for
admins**. Recovery codes are stored hashed and consumed on use, so a stolen
database dump does not yield usable codes.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.utils.security import hash_password, verify_password
from app.utils.totp import (
    generate_recovery_codes,
    generate_secret,
    provisioning_uri,
    verify_code,
)


class MfaError(Exception):
    """User-safe MFA failure."""


class MfaService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def is_required(user: User) -> bool:
        """Admins must hold a second factor."""
        return bool(user.is_admin)

    @staticmethod
    def is_satisfied(user: User) -> bool:
        """True when the account meets the MFA policy for its role."""
        return bool(user.mfa_enabled) or not MfaService.is_required(user)

    async def begin_setup(self, user: User) -> tuple[str, str]:
        """Issue a provisional secret. Not active until a code is confirmed."""
        if user.mfa_enabled:
            raise MfaError("Two-factor authentication is already enabled.")
        secret = generate_secret()
        user.mfa_secret = secret
        await self.db.commit()
        return secret, provisioning_uri(secret, user.email)

    async def activate(self, user: User, code: str) -> list[str]:
        """Confirm enrolment with a live code and return recovery codes once."""
        if not user.mfa_secret:
            raise MfaError("Start two-factor setup first.")
        if user.mfa_enabled:
            raise MfaError("Two-factor authentication is already enabled.")
        if not verify_code(user.mfa_secret, code):
            raise MfaError("That code is not valid. Check your authenticator and retry.")

        plain_codes = generate_recovery_codes()
        user.mfa_recovery_codes = [hash_password(c) for c in plain_codes]
        user.mfa_enabled = True
        await self.db.commit()
        return plain_codes

    async def disable(self, user: User, password: str, code: str) -> None:
        """Turn MFA off. Requires password plus a valid code or recovery code."""
        if not user.mfa_enabled:
            raise MfaError("Two-factor authentication is not enabled.")
        if MfaService.is_required(user):
            raise MfaError("Admin accounts must keep two-factor authentication enabled.")
        if not user.password_hash or not verify_password(password, user.password_hash):
            raise MfaError("Incorrect password.")
        if not await self.verify_challenge(user, code):
            raise MfaError("That code is not valid.")

        user.mfa_enabled = False
        user.mfa_secret = None
        user.mfa_recovery_codes = None
        await self.db.commit()

    async def verify_challenge(self, user: User, code: str) -> bool:
        """Accept either a TOTP code or an unused recovery code.

        A consumed recovery code is removed immediately, making it single-use.
        """
        if not user.mfa_enabled or not user.mfa_secret:
            return False

        submitted = (code or "").strip()
        if not submitted:
            return False

        if verify_code(user.mfa_secret, submitted):
            return True

        stored = list(user.mfa_recovery_codes or [])
        for index, hashed in enumerate(stored):
            if verify_password(submitted, hashed):
                remaining = stored[:index] + stored[index + 1 :]
                user.mfa_recovery_codes = remaining or None
                await self.db.commit()
                return True
        return False

    @staticmethod
    def recovery_codes_remaining(user: User) -> int:
        return len(user.mfa_recovery_codes or [])
