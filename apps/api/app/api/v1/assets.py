"""Scene asset pre-generation endpoints."""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.factory import (
    ProviderUnavailableError,
    get_image_adapter,
    get_storage_adapter,
)
from app.db.session import get_db
from app.deps import get_current_user
from app.models import Project, Scene, SceneAsset, User
from app.schemas.asset import (
    AssetCostPreview,
    AssetPlanState,
    AssetStatusUpdate,
    SceneAssetGroup,
    SceneAssetPublic,
)
from app.services import analytics_service as analytics
from app.services.asset_service import AssetError, AssetService
from app.services.credit_service import (
    InsufficientCreditsError,
    PricingNotConfiguredError,
)
from app.services.project_service import ProjectService
from app.utils.rate_limit import GENERATION_LIMIT, UPLOAD_LIMIT, rate_limited
from app.utils.uploads import MAX_IMAGE_BYTES, UploadValidationError

router = APIRouter(prefix="/projects/{project_id}/assets", tags=["assets"])


async def _load_owned(project_id: uuid.UUID, user: User, db: AsyncSession) -> Project:
    project = await ProjectService(db).get_owned(user.id, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


def _service(db: AsyncSession, with_image: bool = True) -> AssetService:
    """Build the service from whichever providers this environment supplies."""
    try:
        storage = get_storage_adapter()
        image = get_image_adapter() if with_image else None
    except ProviderUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return AssetService(storage, db=db, image=image)


async def _state(project: Project, db: AsyncSession) -> AssetPlanState:
    scenes = list(
        await db.scalars(
            select(Scene).where(Scene.project_id == project.id).order_by(Scene.scene_number)
        )
    )
    groups: list[SceneAssetGroup] = []
    pending = 0
    for scene in scenes:
        assets = list(
            await db.scalars(
                select(SceneAsset)
                .where(SceneAsset.scene_id == scene.id)
                .order_by(SceneAsset.created_at)
            )
        )
        pending += sum(1 for a in assets if a.status == "pending")
        if assets:
            groups.append(
                SceneAssetGroup(
                    scene_number=scene.scene_number,
                    scene_label=(scene.script_data or {}).get("scene_label"),
                    assets=[SceneAssetPublic.model_validate(a) for a in assets],
                )
            )
    return AssetPlanState(project_status=project.status, pending_assets=pending, scenes=groups)


@router.get("", response_model=AssetPlanState)
async def list_assets(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AssetPlanState:
    project = await _load_owned(project_id, user, db)
    return await _state(project, db)


@router.post("/plan", response_model=AssetPlanState)
async def plan_assets(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AssetPlanState:
    """Create pending asset rows from the script. Free; nothing is generated."""
    project = await _load_owned(project_id, user, db)
    service = _service(db, with_image=False)
    try:
        await service.plan_assets(project)
        await db.commit()
    except AssetError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return await _state(project, db)


@router.get("/cost", response_model=AssetCostPreview)
async def asset_cost(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AssetCostPreview:
    project = await _load_owned(project_id, user, db)
    service = _service(db, with_image=False)
    try:
        await service.plan_assets(project)
        await db.commit()
        return AssetCostPreview(**await service.cost_preview(project))
    except AssetError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except PricingNotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.post(
    "/generate",
    response_model=AssetPlanState,
    dependencies=[Depends(rate_limited(GENERATION_LIMIT))],
)
async def generate_assets(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AssetPlanState:
    """Generate every pending reference asset for this project."""
    project = await _load_owned(project_id, user, db)
    service = _service(db)
    try:
        await service.generate_pending(project)
    except InsufficientCreditsError as exc:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"Not enough credits. This needs {exc.required}, you have {exc.available}.",
        ) from exc
    except PricingNotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except AssetError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    state = await _state(project, db)
    generated = sum(
        1
        for group in state.scenes
        for asset in group.assets
        if asset.status in ("generated", "approved")
    )
    await analytics.capture(
        analytics.EVENT_ASSETS_GENERATED,
        distinct_id=str(user.id),
        properties={"generated": generated},
    )
    return state


@router.post(
    "/{asset_id}/regenerate",
    response_model=SceneAssetPublic,
    dependencies=[Depends(rate_limited(GENERATION_LIMIT))],
)
async def regenerate_asset(
    project_id: uuid.UUID,
    asset_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SceneAsset:
    project = await _load_owned(project_id, user, db)
    asset = await _load_asset(project, asset_id, db)
    service = _service(db)
    try:
        return await service.regenerate(project, asset)
    except InsufficientCreditsError as exc:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"Not enough credits. This needs {exc.required}, you have {exc.available}.",
        ) from exc
    except PricingNotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


async def _load_asset(project: Project, asset_id: uuid.UUID, db: AsyncSession) -> SceneAsset:
    """Load an asset, confirming it belongs to a scene of this project."""
    asset = await db.scalar(select(SceneAsset).where(SceneAsset.id == asset_id))
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    scene = await db.scalar(select(Scene).where(Scene.id == asset.scene_id))
    if scene is None or scene.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    return asset


@router.patch("/{asset_id}", response_model=SceneAssetPublic)
async def update_asset_status(
    project_id: uuid.UUID,
    asset_id: uuid.UUID,
    body: AssetStatusUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SceneAsset:
    project = await _load_owned(project_id, user, db)
    asset = await _load_asset(project, asset_id, db)
    return await _service(db, with_image=False).set_status(asset, body.status)


@router.post(
    "/{asset_id}/replace",
    response_model=SceneAssetPublic,
    dependencies=[Depends(rate_limited(UPLOAD_LIMIT))],
)
async def replace_asset(
    project_id: uuid.UUID,
    asset_id: uuid.UUID,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SceneAsset:
    """Swap a generated asset for the user's own image. Never charged."""
    project = await _load_owned(project_id, user, db)
    asset = await _load_asset(project, asset_id, db)

    raw = await file.read(MAX_IMAGE_BYTES + 1)
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File exceeds the {MAX_IMAGE_BYTES // (1024 * 1024)} MB limit.",
        )

    service = _service(db, with_image=False)
    try:
        stored = await service.upload_brand_asset(user.id, project.id, raw)
    except UploadValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    asset.image_url = stored["key"]
    asset.status = "user_uploaded"
    await db.commit()
    await db.refresh(asset)
    return asset


@router.post("/approve", response_model=AssetPlanState)
async def approve_assets(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AssetPlanState:
    """Approve generated assets and attach them as video references."""
    project = await _load_owned(project_id, user, db)
    await _service(db, with_image=False).approve_all(project)
    return await _state(project, db)
