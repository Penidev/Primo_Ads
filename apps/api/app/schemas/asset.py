"""Scene asset schemas."""

import uuid

from pydantic import BaseModel, Field


class SceneAssetPublic(BaseModel):
    id: uuid.UUID
    scene_id: uuid.UUID
    asset_type: str | None = None
    description: str | None = None
    image_url: str | None = None
    status: str

    model_config = {"from_attributes": True}


class SceneAssetGroup(BaseModel):
    """Assets grouped under their scene, for the review screen."""

    scene_number: int
    scene_label: str | None = None
    assets: list[SceneAssetPublic]


class AssetPlanState(BaseModel):
    project_status: str
    pending_assets: int
    scenes: list[SceneAssetGroup]


class AssetCostPreview(BaseModel):
    pending_assets: int
    credits_required: float
    estimated_usd: float
    current_balance: float
    sufficient: bool


class AssetStatusUpdate(BaseModel):
    status: str = Field(pattern="^(approved|rejected)$")
