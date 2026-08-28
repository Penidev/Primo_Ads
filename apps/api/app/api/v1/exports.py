"""Export endpoints: script documents and the finished video."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.factory import ProviderUnavailableError, get_storage_adapter
from app.db.session import get_db
from app.deps import get_current_user
from app.models import Project, User
from app.schemas.script import GeneratedScript
from app.services.export_service import (
    to_markdown,
    to_prompt_list,
    to_shot_list_csv,
)
from app.services.project_service import ProjectService
from app.services.stitch_service import StitchError, StitchService

router = APIRouter(prefix="/projects/{project_id}/export", tags=["export"])


async def _load_owned(project_id: uuid.UUID, user: User, db: AsyncSession) -> Project:
    project = await ProjectService(db).get_owned(user.id, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


def _script_of(project: Project) -> GeneratedScript:
    if not project.script:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No script generated yet")
    return GeneratedScript.model_validate(project.script)


def _brand_name(project: Project) -> str | None:
    brand = (project.brief or {}).get("brand") or {}
    name = brand.get("name")
    return name if isinstance(name, str) else None


def _attachment(content: str, media_type: str, filename: str) -> PlainTextResponse:
    return PlainTextResponse(
        content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/treatment", response_class=PlainTextResponse)
async def export_treatment(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    """Director's treatment as Markdown (opens in any editor or Google Docs)."""
    project = await _load_owned(project_id, user, db)
    body = to_markdown(_script_of(project), _brand_name(project))
    return _attachment(body, "text/markdown; charset=utf-8", "treatment.md")


@router.get("/shot-list", response_class=PlainTextResponse)
async def export_shot_list(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    """Shot list as CSV for the camera department."""
    project = await _load_owned(project_id, user, db)
    body = to_shot_list_csv(_script_of(project))
    return _attachment(body, "text/csv; charset=utf-8", "shot-list.csv")


@router.get("/prompts", response_class=PlainTextResponse)
async def export_prompts(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    """Raw video prompts, for use in other tools."""
    project = await _load_owned(project_id, user, db)
    body = to_prompt_list(_script_of(project))
    return _attachment(body, "text/plain; charset=utf-8", "prompts.txt")


@router.get("/video")
async def export_video(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Short-lived signed URL for the finished master video."""
    project = await _load_owned(project_id, user, db)
    try:
        service = StitchService(db, get_storage_adapter())
        return {"url": await service.signed_download_url(project)}
    except StitchError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ProviderUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
