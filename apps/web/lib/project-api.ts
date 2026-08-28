import { api } from "./api";
import type { ProjectDetail, ProjectSummary } from "@/types/project";

export const projectApi = {
  list: () => api.get<ProjectSummary[]>("/projects"),

  create: (title: string | null, brief: Record<string, unknown> = {}) =>
    api.post<ProjectDetail>("/projects", { title, brief }),

  get: (id: string) => api.get<ProjectDetail>(`/projects/${id}`),

  updateBrief: (id: string, patch: { title?: string; brief?: Record<string, unknown> }) =>
    api.patch<ProjectDetail>(`/projects/${id}`, patch),

  remove: (id: string) => api.del<void>(`/projects/${id}`),
};
