"""Video model catalogue and per-model cost preview.

The catalogue is driven entirely by the `video_models` table, so admins can add,
retire, or reprice engines with no deployment (Requirements 8.4, 8.5).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_current_user
from app.models import Scene, User, VideoModel
from app.schemas.video_model import ModelCostPreview, VideoModelPublic
from app.services.credit_service import CreditService, PricingNotConfiguredError
from app.services.project_service import ProjectService

router = APIRouter(prefix="/video-models", tags=["video-models"])


@router.get("", response_model=list[VideoModelPublic])
async def list_models(
    aspect_ratio: str | None = Query(default=None),
    requires_audio: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[VideoModel]:
    """Enabled engines, optionally filtered by what the brief needs."""
    stmt = select(VideoModel).where(VideoModel.is_enabled.is_(True))
    if requires_audio:
        stmt = stmt.where(VideoModel.supports_audio.is_(True))
    rows = list(await db.scalars(stmt.order_by(VideoModel.credit_multiplier)))

    if aspect_ratio:
        rows = [
            m
            for m in rows
            if not m.supported_aspect_ratios or aspect_ratio in m.supported_aspect_ratios
        ]
    return rows


@router.get("/recommended", response_model=VideoModelPublic)
async def recommended_model(
    requires_audio: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> VideoModel:
    """Pick a sensible default: cheapest enabled engine meeting the requirement."""
    stmt = select(VideoModel).where(VideoModel.is_enabled.is_(True))
    if requires_audio:
        stmt = stmt.where(VideoModel.supports_audio.is_(True))
    model = await db.scalar(stmt.order_by(VideoModel.credit_multiplier).limit(1))
    if model is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "No video models are currently available."
        )
    return model


@router.get("/{model_slug}/cost", response_model=ModelCostPreview)
async def model_cost(
    model_slug: str,
    project_id: uuid.UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ModelCostPreview:
    """Exact credit cost to generate this project's scenes with this engine."""
    project = await ProjectService(db).get_owned(user.id, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    scene_count = len(list(await db.scalars(select(Scene).where(Scene.project_id == project.id))))
    if scene_count == 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Generate a script before pricing video generation."
        )

    service = CreditService(db)
    try:
        required = await service.video_scene_cost(model_slug, scene_count)
    except PricingNotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    balance = await service.get_balance(user.id)
    return ModelCostPreview(
        model_slug=model_slug,
        scene_count=scene_count,
        credits_required=float(required),
        estimated_usd=float(await service.quote_usd(required)),
        current_balance=float(balance),
        sufficient=balance >= required,
    )
