"""Script generation endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.factory import ProviderUnavailableError, get_llm_adapter
from app.adapters.llm.gemini import LLMRequestError
from app.db.session import get_db
from app.deps import get_current_user
from app.models import Project, User
from app.schemas.script import (
    GeneratedScript,
    ScriptCostPreview,
    ScriptGenerateRequest,
)
from app.services import analytics_service as analytics
from app.services.credit_service import (
    InsufficientCreditsError,
    PricingNotConfiguredError,
)
from app.services.project_service import ProjectService
from app.services.script_service import (
    ContentRefusedError,
    ScriptGenerationError,
    ScriptService,
)
from app.utils.rate_limit import GENERATION_LIMIT, rate_limited

router = APIRouter(prefix="/projects/{project_id}/script", tags=["scripts"])


async def _load_owned(project_id: uuid.UUID, user: User, db: AsyncSession) -> Project:
    project = await ProjectService(db).get_owned(user.id, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


def _service(db: AsyncSession) -> ScriptService:
    """Build the service with whichever LLM provider this environment supplies."""
    try:
        return ScriptService(db, get_llm_adapter())
    except ProviderUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.get("/cost", response_model=ScriptCostPreview)
async def script_cost(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScriptCostPreview:
    """Show the exact credit cost before the user commits."""
    await _load_owned(project_id, user, db)
    try:
        preview = await _service(db).cost_preview(user.id)
    except PricingNotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return ScriptCostPreview(**preview)


@router.post(
    "",
    response_model=GeneratedScript,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limited(GENERATION_LIMIT))],
)
async def generate_script(
    project_id: uuid.UUID,
    body: ScriptGenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GeneratedScript:
    project = await _load_owned(project_id, user, db)
    service = _service(db)
    try:
        script = await service.generate(
            project,
            ad_category=body.ad_category,
            aspect_ratio=body.aspect_ratio,
            target_duration_seconds=body.target_duration_seconds,
        )
    except InsufficientCreditsError as exc:
        await analytics.capture(
            analytics.EVENT_INSUFFICIENT_CREDITS,
            distinct_id=str(user.id),
            properties={"action": "script_generation", "required": float(exc.required)},
        )
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"Not enough credits. This needs {exc.required}, you have {exc.available}.",
        ) from exc
    except PricingNotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except ContentRefusedError as exc:
        await analytics.capture(
            analytics.EVENT_CONTENT_REFUSED,
            distinct_id=str(user.id),
            properties={"stage": "script"},
        )
        # 422: the request was understood but its content is not permitted.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except ScriptGenerationError as exc:
        await analytics.capture(
            analytics.EVENT_GENERATION_FAILED,
            distinct_id=str(user.id),
            properties={"stage": "script"},
        )
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    except LLMRequestError as exc:
        await analytics.capture(
            analytics.EVENT_GENERATION_FAILED,
            distinct_id=str(user.id),
            properties={"stage": "script", "reason": "provider_unavailable"},
        )
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "The generation provider is unavailable. Please try again.",
        ) from exc

    await analytics.capture(
        analytics.EVENT_SCRIPT_GENERATED,
        distinct_id=str(user.id),
        properties={
            "scene_count": len(script.scenes),
            "duration_seconds": script.total_duration_seconds,
            "ad_category": body.ad_category,
        },
    )
    return script


@router.get("", response_model=GeneratedScript)
async def get_script(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GeneratedScript:
    project = await _load_owned(project_id, user, db)
    if not project.script:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No script generated yet")
    return GeneratedScript.model_validate(project.script)
