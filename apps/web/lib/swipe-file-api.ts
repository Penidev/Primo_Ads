import { api } from "./api";
import type {
  BlueprintDetail,
  BlueprintStats,
  BlueprintSummary,
} from "@/types/blueprint";

export interface BlueprintEdits {
  title?: string;
  industry?: string;
  ad_category?: string;
  hook_style?: string;
  pacing?: string;
  format?: string;
  platform?: string;
  effectiveness_score?: number;
}

const BASE = "/admin/swipe-file";

export const swipeFileApi = {
  stats: () => api.get<BlueprintStats>(`${BASE}/stats`),

  list: (params: { approved?: boolean; category?: string } = {}) => {
    const query = new URLSearchParams();
    if (params.approved !== undefined) query.set("approved", String(params.approved));
    if (params.category) query.set("ad_category", params.category);
    const suffix = query.toString() ? `?${query}` : "";
    return api.get<BlueprintSummary[]>(`${BASE}${suffix}`);
  },

  get: (id: string) => api.get<BlueprintDetail>(`${BASE}/${id}`),

  update: (id: string, edits: BlueprintEdits) =>
    api.patch<BlueprintDetail>(`${BASE}/${id}`, edits),

  setApproval: (id: string, isApproved: boolean, effectivenessScore?: number) =>
    api.post<BlueprintDetail>(`${BASE}/${id}/approval`, {
      is_approved: isApproved,
      effectiveness_score: effectivenessScore ?? null,
    }),

  regenerateEmbedding: (id: string) =>
    api.post<{ has_embedding: boolean }>(`${BASE}/${id}/embedding`),

  remove: (id: string) => api.del<void>(`${BASE}/${id}`),

  /** Multipart upload; bypasses the JSON client so the browser sets boundaries. */
  analyze: async (
    file: File,
    hints: { industry?: string; category?: string } = {}
  ): Promise<BlueprintDetail> => {
    const form = new FormData();
    form.append("file", file);
    if (hints.industry) form.append("industry_hint", hints.industry);
    if (hints.category) form.append("category_hint", hints.category);

    const response = await fetch(`/api/backend${BASE}/analyze`, {
      method: "POST",
      body: form,
      credentials: "include",
    });
    if (!response.ok) {
      let message = response.statusText;
      try {
        const body = await response.json();
        message = body.detail || message;
      } catch {
        // keep statusText
      }
      throw new Error(message);
    }
    return response.json() as Promise<BlueprintDetail>;
  },
};
