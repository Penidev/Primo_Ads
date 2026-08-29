"""Admin swipe-file curation endpoints.

Reference ads are internal curation material: they are stored privately, never
served to end users, and only the derived structural blueprint is ever used at
generation time.
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.factory import (
    ProviderUnavailableError,
    get_llm_adapter,
    get_optional_storage_adapter,
)
from app.adapters.llm.gemini import LLMRequestError
from app.db.session import get_db
from app.deps import get_current_admin
from app.models import AdBlueprint
from app.schemas.blueprint import (
    BlueprintApproval,
    BlueprintDetail,
    BlueprintStats,
    BlueprintSummary,
    BlueprintUpdate,
)
from app.services.swipe_file_service import BlueprintAnalysisError, SwipeFileService
from app.utils.rate_limit import GENERATION_LIMIT, rate_limited
from app.utils.uploads import MAX_VIDEO_BYTES, UploadValidationError

router = APIRouter(
    prefix="/admin/swipe-file",
    tags=["admin-swipe-file"],
    dependencies=[Depends(get_current_admin)],
)


def _service(db: AsyncSession) -> SwipeFileService:
    try:
        llm = get_llm_adapter()
    except ProviderUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    # Storage is optional here: analysis works without retaining the source file.
    return SwipeFileService(db, llm, get_optional_storage_adapter())


def _to_detail(blueprint: AdBlueprint) -> BlueprintDetail:
    return BlueprintDetail(
        id=blueprint.id,
        title=blueprint.title,
        industry=blueprint.industry,
        ad_category=blueprint.ad_category,
        duration_seconds=blueprint.duration_seconds,
        format=blueprint.format,
        pacing=blueprint.pacing,
        hook_style=blueprint.hook_style,
        effectiveness_score=blueprint.effectiveness_score,
        is_approved=blueprint.is_approved,
        has_embedding=blueprint.embedding is not None,
        created_at=blueprint.created_at,
        psychological_triggers=blueprint.psychological_triggers,
        camera_techniques=blueprint.camera_techniques,
        color_palette=blueprint.color_palette,
        structural_arc=blueprint.structural_arc,
        full_analysis=blueprint.full_analysis,
        platform=blueprint.platform,
    )


def _to_summary(blueprint: AdBlueprint) -> BlueprintSummary:
    return BlueprintSummary(
        id=blueprint.id,
        title=blueprint.title,
        industry=blueprint.industry,
        ad_category=blueprint.ad_category,
        duration_seconds=blueprint.duration_seconds,
        format=blueprint.format,
        pacing=blueprint.pacing,
        hook_style=blueprint.hook_style,
        effectiveness_score=blueprint.effectiveness_score,
        is_approved=blueprint.is_approved,
        has_embedding=blueprint.embedding is not None,
        created_at=blueprint.created_at,
    )


@router.get("/stats", response_model=BlueprintStats)
async def library_stats(db: AsyncSession = Depends(get_db)) -> BlueprintStats:
    """Coverage overview: totals plus breakdowns by category and industry."""
    return BlueprintStats(**await _service(db).stats())


@router.get("", response_model=list[BlueprintSummary])
async def list_blueprints(
    approved: bool | None = Query(default=None),
    ad_category: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[BlueprintSummary]:
    blueprints = await _service(db).list_blueprints(
        approved=approved, ad_category=ad_category, limit=limit
    )
    return [_to_summary(b) for b in blueprints]


@router.post(
    "/analyze",
    response_model=BlueprintDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limited(GENERATION_LIMIT))],
)
async def analyze_reference_ad(
    file: UploadFile = File(...),
    industry_hint: str | None = Form(default=None, max_length=100),
    category_hint: str | None = Form(default=None, max_length=100),
    db: AsyncSession = Depends(get_db),
) -> BlueprintDetail:
    """Upload a reference ad and deconstruct it into a pending blueprint."""
    raw = await file.read(MAX_VIDEO_BYTES + 1)
    if len(raw) > MAX_VIDEO_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Video exceeds the {MAX_VIDEO_BYTES // (1024 * 1024)} MB limit.",
        )

    try:
        blueprint = await _service(db).ingest_video(
            raw, industry_hint=industry_hint, category_hint=category_hint
        )
    except UploadValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except BlueprintAnalysisError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    except LLMRequestError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "The analysis provider is unavailable. Please try again.",
        ) from exc
    return _to_detail(blueprint)


@router.get("/{blueprint_id}", response_model=BlueprintDetail)
async def get_blueprint(
    blueprint_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> BlueprintDetail:
    blueprint = await _service(db).get(blueprint_id)
    if blueprint is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Blueprint not found")
    return _to_detail(blueprint)


@router.patch("/{blueprint_id}", response_model=BlueprintDetail)
async def update_blueprint(
    blueprint_id: uuid.UUID,
    body: BlueprintUpdate,
    db: AsyncSession = Depends(get_db),
) -> BlueprintDetail:
    """Curator corrections to the extracted metadata."""
    service = _service(db)
    blueprint = await service.get(blueprint_id)
    if blueprint is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Blueprint not found")
    updated = await service.apply_edits(blueprint, body.model_dump(exclude_unset=True))
    return _to_detail(updated)


@router.post("/{blueprint_id}/approval", response_model=BlueprintDetail)
async def set_approval(
    blueprint_id: uuid.UUID,
    body: BlueprintApproval,
    db: AsyncSession = Depends(get_db),
) -> BlueprintDetail:
    """Approve or unapprove. Only approved blueprints reach script generation."""
    service = _service(db)
    blueprint = await service.get(blueprint_id)
    if blueprint is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Blueprint not found")
    updated = await service.set_approval(blueprint, body.is_approved, body.effectiveness_score)
    return _to_detail(updated)


@router.post("/{blueprint_id}/embedding")
async def regenerate_embedding(
    blueprint_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> dict[str, bool]:
    """Rebuild the similarity vector after edits."""
    service = _service(db)
    blueprint = await service.get(blueprint_id)
    if blueprint is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Blueprint not found")
    return {"has_embedding": await service.regenerate_embedding(blueprint)}


@router.delete("/{blueprint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_blueprint(blueprint_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    service = _service(db)
    blueprint = await service.get(blueprint_id)
    if blueprint is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Blueprint not found")
    await service.delete(blueprint)
