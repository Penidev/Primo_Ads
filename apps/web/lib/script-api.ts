import { api } from "./api";
import type { GeneratedScript, ScriptCostPreview } from "@/types/script";

export interface GenerateScriptOptions {
  ad_category?: string;
  aspect_ratio?: "9:16" | "16:9" | "1:1";
  target_duration_seconds?: number;
}

export const scriptApi = {
  cost: (projectId: string) =>
    api.get<ScriptCostPreview>(`/projects/${projectId}/script/cost`),

  get: (projectId: string) =>
    api.get<GeneratedScript>(`/projects/${projectId}/script`),

  generate: (projectId: string, options: GenerateScriptOptions = {}) =>
    api.post<GeneratedScript>(`/projects/${projectId}/script`, options),
};
