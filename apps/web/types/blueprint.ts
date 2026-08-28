export interface BlueprintSummary {
  id: string;
  title: string | null;
  industry: string | null;
  ad_category: string | null;
  duration_seconds: number | null;
  format: string | null;
  pacing: string | null;
  hook_style: string | null;
  effectiveness_score: number | null;
  is_approved: boolean;
  has_embedding: boolean;
  created_at: string;
}

export interface BlueprintBeat {
  beat_number: number;
  label: string;
  start_second: number;
  end_second: number;
  narrative_function: string;
  visual_technique: string;
  message_intent: string;
}

export interface StructuralArc {
  beats?: BlueprintBeat[];
  why_it_works?: string;
  reusable_pattern?: string;
}

export interface BlueprintDetail extends BlueprintSummary {
  psychological_triggers: string[] | null;
  camera_techniques: string[] | null;
  color_palette: string[] | null;
  structural_arc: StructuralArc | null;
  full_analysis: string | null;
  platform: string | null;
}

export interface BlueprintStats {
  total: number;
  approved: number;
  pending: number;
  with_embeddings: number;
  by_category: Record<string, number>;
  by_industry: Record<string, number>;
}

export const BLUEPRINT_CATEGORIES = [
  "problem-agitation-solution",
  "us-vs-competitor",
  "social-proof",
  "high-energy-disruptor",
  "emotional-storytelling",
  "product-demo",
] as const;
