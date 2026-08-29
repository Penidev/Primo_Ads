"""Video generation endpoints."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.video.base import VideoProviderError
from app.db.session import get_db
from app.deps import get_current_user
from app.models import Project, Scene, User
from app.schemas.generation import (
    GenerationState,
    RerollRequest,
    StartGenerationRequest,
)
from app.services import analytics_service as analytics
from app.services.credit_service import (
    InsufficientCreditsError,
    PricingNotConfiguredError,
)
from app.services.project_service import ProjectService
from app.services.video_service import VideoGenerationError, VideoService
from app.utils.rate_limit import GENERATION_LIMIT, rate_limited

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}/generation", tags=["generation"])

MAX_CONCURRENT_PROJECTS = 3


def _enqueue_polling(project_id: uuid.UUID) -> None:
    """Hand off progress tracking and stitching to a background worker.

    If the broker is unreachable the request still succeeds: scenes were already
    submitted to the provider, and the status endpoint polls them on demand.
    """
    try:
        from app.workers.video_tasks import poll_project

        poll_project.delay(str(project_id))
    except Exception:
        # Deliberately swallowed: the scenes are already submitted, so failing the
        # request would be wrong. Logged as a warning because a broker that is
        # persistently down means nothing gets stitched without a manual poll.
        logger.warning(
            "Could not enqueue polling for project %s; falling back to on-demand status polling.",
            project_id,
            exc_info=True,
        )


async def _load_owned(project_id: uuid.UUID, user: User, db: AsyncSession) -> Project:
    project = await ProjectService(db).get_owned(user.id, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


def _state(project: Project, scenes: list[Scene]) -> GenerationState:
    return GenerationState(
        project_status=project.status,
        selected_model_slug=project.selected_model_slug,
        final_video_url=project.final_video_url,
        scenes=scenes,  # type: ignore[arg-type]
    )


async def _assert_concurrency_budget(user: User, db: AsyncSession) -> None:
    """Cap simultaneous generating projects to contain provider spend."""
    active = await db.scalars(
        select(Project).where(
            Project.user_id == user.id,
            Project.status == "generating",
            Project.deleted_at.is_(None),
        )
    )
    if len(list(active)) >= MAX_CONCURRENT_PROJECTS:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "You already have the maximum number of generations running. Wait for one to finish.",
        )


@router.post(
    "",
    response_model=GenerationState,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limited(GENERATION_LIMIT))],
)
async def start_generation(
    project_id: uuid.UUID,
    body: StartGenerationRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GenerationState:
    project = await _load_owned(project_id, user, db)
    await _assert_concurrency_budget(user, db)

    service = VideoService(db)
    try:
        scenes = await service.start_generation(project, body.model_slug)
        _enqueue_polling(project.id)
    except InsufficientCreditsError as exc:
        await analytics.capture(
            analytics.EVENT_INSUFFICIENT_CREDITS,
            distinct_id=str(user.id),
            properties={"action": "video_generation", "required": float(exc.required)},
        )
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"Not enough credits. This needs {exc.required}, you have {exc.available}.",
        ) from exc
    except PricingNotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except VideoGenerationError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except VideoProviderError as exc:
        await analytics.capture(
            analytics.EVENT_GENERATION_FAILED,
            distinct_id=str(user.id),
            properties={"stage": "video", "model": body.model_slug},
        )
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    await analytics.capture(
        analytics.EVENT_VIDEO_GENERATION_STARTED,
        distinct_id=str(user.id),
        properties={"model": body.model_slug, "scene_count": len(scenes)},
    )
    return _state(project, scenes)


@router.get("", response_model=GenerationState)
async def generation_status(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GenerationState:
    """Current per-scene progress; polls the provider for in-flight scenes."""
    project = await _load_owned(project_id, user, db)
    scenes = await VideoService(db).refresh_project(project)
    return _state(project, scenes)


@router.post(
    "/scenes/{scene_number}/reroll",
    response_model=GenerationState,
    dependencies=[Depends(rate_limited(GENERATION_LIMIT))],
)
async def reroll_scene(
    project_id: uuid.UUID,
    scene_number: int,
    body: RerollRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GenerationState:
    project = await _load_owned(project_id, user, db)
    scene = await db.scalar(
        select(Scene).where(Scene.project_id == project.id, Scene.scene_number == scene_number)
    )
    if scene is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scene not found")

    service = VideoService(db)
    try:
        await service.reroll_scene(project, scene, body.model_slug)
    except InsufficientCreditsError as exc:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"Not enough credits. This needs {exc.required}, you have {exc.available}.",
        ) from exc
    except PricingNotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except VideoGenerationError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    await analytics.capture(
        analytics.EVENT_SCENE_REROLLED,
        distinct_id=str(user.id),
        properties={"scene_number": scene_number},
    )
    scenes = await service.refresh_project(project)
    return _state(project, scenes)
