"""User profile and onboarding schemas."""

import uuid

from pydantic import BaseModel, EmailStr, Field


class OnboardingUpdate(BaseModel):
    """Progressive onboarding — every field optional so steps can be skipped."""

    full_name: str | None = Field(default=None, max_length=255)
    company_name: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, min_length=2, max_length=3)
    industry: str | None = Field(default=None, max_length=100)
    company_size: str | None = Field(default=None, max_length=50)
    role: str | None = Field(default=None, max_length=50)
    use_case: str | None = Field(default=None, max_length=50)
    ad_platforms: list[str] | None = None
    complete: bool = False  # set true on the final step


class UserProfile(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    company_name: str | None = None
    country: str | None = None
    industry: str | None = None
    company_size: str | None = None
    role: str | None = None
    use_case: str | None = None
    ad_platforms: list[str] | None = None
    is_admin: bool = False
    onboarding_completed: bool = False

    model_config = {"from_attributes": True}
