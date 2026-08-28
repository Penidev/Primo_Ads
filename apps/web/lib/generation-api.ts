import { api } from "./api";
import type {
  GenerationState,
  ModelCostPreview,
  VideoModelPublic,
} from "@/types/generation";

export const generationApi = {
  listModels: (params: { aspectRatio?: string; requiresAudio?: boolean } = {}) => {
    const query = new URLSearchParams();
    if (params.aspectRatio) query.set("aspect_ratio", params.aspectRatio);
    if (params.requiresAudio) query.set("requires_audio", "true");
    const suffix = query.toString() ? `?${query}` : "";
    return api.get<VideoModelPublic[]>(`/video-models${suffix}`);
  },

  modelCost: (modelSlug: string, projectId: string) =>
    api.get<ModelCostPreview>(
      `/video-models/${modelSlug}/cost?project_id=${encodeURIComponent(projectId)}`
    ),

  start: (projectId: string, modelSlug: string) =>
    api.post<GenerationState>(`/projects/${projectId}/generation`, {
      model_slug: modelSlug,
    }),

  status: (projectId: string) =>
    api.get<GenerationState>(`/projects/${projectId}/generation`),

  reroll: (projectId: string, sceneNumber: number, modelSlug?: string) =>
    api.post<GenerationState>(
      `/projects/${projectId}/generation/scenes/${sceneNumber}/reroll`,
      { model_slug: modelSlug ?? null }
    ),
};
