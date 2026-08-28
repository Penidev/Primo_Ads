export interface AssetRequirement {
  asset_type: string;
  description: string;
  style: string | null;
}

export interface SceneScript {
  scene_number: number;
  scene_label: string | null;
  duration_seconds: number;
  script_text: string;
  voiceover_direction: string | null;
  visual_description: string;
  camera_movement: string | null;
  color_grading: string | null;
  lighting: string | null;
  audio_sfx: string | null;
  graphics_overlay: string | null;
  brand_elements: string | null;
  video_prompt: string;
  image_gen_needed: AssetRequirement[];
}

export interface GeneratedScript {
  campaign_title: string;
  total_duration_seconds: number;
  scenes: SceneScript[];
  music_direction: string | null;
  overall_color_palette: string | null;
  target_emotion_arc: string | null;
}

export interface ScriptCostPreview {
  credits_required: number;
  estimated_usd: number;
  current_balance: number;
  sufficient: boolean;
}
