"""MFA enrolment and challenge schemas."""

from pydantic import BaseModel, Field


class MfaSetupResponse(BaseModel):
    """Returned when enrolment begins. The secret is shown once."""

    secret: str
    provisioning_uri: str


class MfaActivateRequest(BaseModel):
    code: str = Field(min_length=6, max_length=10)


class MfaActivateResponse(BaseModel):
    """Recovery codes are shown once and stored hashed."""

    recovery_codes: list[str]


class MfaDisableRequest(BaseModel):
    """Disabling requires both the password and a live code."""

    password: str = Field(min_length=1, max_length=128)
    code: str = Field(min_length=6, max_length=20)


class MfaStatusResponse(BaseModel):
    mfa_enabled: bool
    mfa_required: bool
    recovery_codes_remaining: int


class TosAcceptRequest(BaseModel):
    version: str = Field(min_length=1, max_length=20)
