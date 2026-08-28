"""User profile and onboarding endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas.user import OnboardingUpdate, UserProfile
from app.services import analytics_service as analytics

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserProfile)
async def get_profile(user: User = Depends(get_current_user)) -> User:
    return user


@router.patch("/me/onboarding", response_model=UserProfile)
async def update_onboarding(
    body: OnboardingUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Persist onboarding fields. Partial updates supported (skip/resume)."""
    data = body.model_dump(exclude_unset=True, exclude={"complete"})
    for field, value in data.items():
        setattr(user, field, value)
    if body.complete:
        user.onboarding_completed = True
    await db.commit()
    await db.refresh(user)

    if body.complete:
        # Segment traits only — never email or name.
        await analytics.identify(
            str(user.id),
            traits={
                "country": user.country,
                "industry": user.industry,
                "role": user.role,
                "use_case": user.use_case,
                "company_size": user.company_size,
            },
        )
        await analytics.capture(
            analytics.EVENT_ONBOARDING_COMPLETED, distinct_id=str(user.id)
        )
    return user
