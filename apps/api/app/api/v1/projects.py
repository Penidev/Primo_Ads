"""Project endpoints — all enforce per-user ownership."""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.factory import ProviderUnavailableError, get_storage_adapter
from app.db.session import get_db
from app.deps import get_current_user
from app.models import Project, User
from app.schemas.project import (
    ProjectBriefUpdate,
    ProjectCreate,
    ProjectDetail,
    ProjectSummary,
)
from app.services.asset_service import AssetService
from app.services.project_service import ProjectService
from app.utils.rate_limit import UPLOAD_LIMIT, rate_limited
from app.utils.uploads import MAX_IMAGE_BYTES, UploadValidationError

router = APIRouter(prefix="/projects", tags=["projects"])


async def _load_owned(
    project_id: uuid.UUID, user: User, db: AsyncSession
) -> Project:
    project = await ProjectService(db).get_owned(user.id, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


@router.get("", response_model=list[ProjectSummary])
async def list_projects(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Project]:
    return await ProjectService(db).list_for_user(user.id)


@router.post("", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    return await ProjectService(db).create(user.id, body.title, body.brief)


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    return await _load_owned(project_id, user, db)


@router.patch("/{project_id}", response_model=ProjectDetail)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectBriefUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    project = await _load_owned(project_id, user, db)
    return await ProjectService(db).update_brief(project, body.title, body.brief)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    project = await _load_owned(project_id, user, db)
    await ProjectService(db).soft_delete(project)


@router.post(
    "/{project_id}/brand-assets",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limited(UPLOAD_LIMIT))],
)
async def upload_brand_asset(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Upload a brand or character image for this project.

    Distinct from scene assets (`/assets`): these are the brand's own materials
    used as references. The file is validated by magic bytes and re-encoded before
    storage; the client-supplied filename and content type are never trusted.
    """
    await _load_owned(project_id, user, db)

    # Read with a hard cap so an oversized body can't exhaust memory.
    raw = await file.read(MAX_IMAGE_BYTES + 1)
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File exceeds the {MAX_IMAGE_BYTES // (1024 * 1024)} MB limit.",
        )

    try:
        service = AssetService(get_storage_adapter())
        return await service.upload_brand_asset(user.id, project_id, raw)
    except UploadValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except ProviderUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
