"""Auth request/response schemas."""

import uuid

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    # Supplied on the second step when the account has MFA enabled.
    mfa_code: str | None = Field(default=None, max_length=20)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    # refresh token is delivered as an httpOnly cookie, not in the body


class MfaChallengeResponse(BaseModel):
    """Returned instead of tokens when a second factor is needed."""

    mfa_required: bool = True
    detail: str = "Enter the code from your authenticator app."


class MfaEnrolmentRequiredResponse(BaseModel):
    """Admin has no second factor yet; enrolment must happen before access."""

    mfa_enrolment_required: bool = True
    detail: str = "Admin accounts must set up two-factor authentication."


class UserPublic(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    is_admin: bool = False
    onboarding_completed: bool = False

    model_config = {"from_attributes": True}


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=10, max_length=128)
