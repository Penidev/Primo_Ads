import { api } from "./api";
import type {
  AssetCostPreview,
  AssetPlanState,
  SceneAssetPublic,
} from "@/types/asset";

const base = (projectId: string) => `/projects/${projectId}/assets`;

export const assetApi = {
  list: (projectId: string) => api.get<AssetPlanState>(base(projectId)),

  plan: (projectId: string) => api.post<AssetPlanState>(`${base(projectId)}/plan`),

  cost: (projectId: string) => api.get<AssetCostPreview>(`${base(projectId)}/cost`),

  generate: (projectId: string) =>
    api.post<AssetPlanState>(`${base(projectId)}/generate`),

  regenerate: (projectId: string, assetId: string) =>
    api.post<SceneAssetPublic>(`${base(projectId)}/${assetId}/regenerate`),

  setStatus: (projectId: string, assetId: string, status: "approved" | "rejected") =>
    api.patch<SceneAssetPublic>(`${base(projectId)}/${assetId}`, { status }),

  approveAll: (projectId: string) =>
    api.post<AssetPlanState>(`${base(projectId)}/approve`),

  /** Multipart replace; bypasses the JSON client so the browser sets boundaries. */
  replace: async (
    projectId: string,
    assetId: string,
    file: File
  ): Promise<SceneAssetPublic> => {
    const form = new FormData();
    form.append("file", file);
    const response = await fetch(
      `/api/backend/projects/${projectId}/assets/${assetId}/replace`,
      { method: "POST", body: form, credentials: "include" }
    );
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
    return response.json() as Promise<SceneAssetPublic>;
  },
};
