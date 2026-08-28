export type AssetStatus =
  | "pending"
  | "generated"
  | "approved"
  | "rejected"
  | "user_uploaded"
  | "failed";

export interface SceneAssetPublic {
  id: string;
  scene_id: string;
  asset_type: string | null;
  description: string | null;
  image_url: string | null;
  status: AssetStatus | string;
}

export interface SceneAssetGroup {
  scene_number: number;
  scene_label: string | null;
  assets: SceneAssetPublic[];
}

export interface AssetPlanState {
  project_status: string;
  pending_assets: number;
  scenes: SceneAssetGroup[];
}

export interface AssetCostPreview {
  pending_assets: number;
  credits_required: number;
  estimated_usd: number;
  current_balance: number;
  sufficient: boolean;
}
