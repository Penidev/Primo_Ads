export interface ProjectSummary {
  id: string;
  title: string | null;
  status: string;
  total_credits_spent: number;
  final_video_url: string | null;
  updated_at: string;
  created_at: string;
}

export interface ProjectDetail extends ProjectSummary {
  brief: Record<string, unknown>;
  script: Record<string, unknown> | null;
  selected_model_slug: string | null;
}
