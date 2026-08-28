export interface VideoModelPublic {
  slug: string;
  display_name: string | null;
  provider: string | null;
  quality_tier: string | null;
  max_duration_seconds: number | null;
  supported_resolutions: string[] | null;
  supported_aspect_ratios: string[] | null;
  supports_audio: boolean;
  supports_image_reference: boolean;
  credit_multiplier: number;
  avg_generation_time_seconds: number | null;
}

export interface ModelCostPreview {
  model_slug: string;
  scene_count: number;
  credits_required: number;
  estimated_usd: number;
  current_balance: number;
  sufficient: boolean;
}

export type SceneStatus = "pending" | "generating" | "completed" | "failed";

export interface ScenePublic {
  id: string;
  scene_number: number;
  duration_seconds: number | null;
  generation_status: SceneStatus | string;
  model_slug: string | null;
  video_url: string | null;
  thumbnail_url: string | null;
  error_message: string | null;
}

export interface GenerationState {
  project_status: string;
  selected_model_slug: string | null;
  final_video_url: string | null;
  scenes: ScenePublic[];
}
