import { api } from "./api";

export interface ActionPricing {
  action_key: string;
  display_name: string | null;
  base_credits: number;
  unit: string | null;
  is_enabled: boolean;
  notes: string | null;
  updated_at: string;
}

export interface VideoModelAdmin {
  slug: string;
  display_name: string | null;
  provider: string | null;
  model_id: string | null;
  is_enabled: boolean;
  quality_tier: string | null;
  supports_audio: boolean;
  supports_image_reference: boolean;
  max_duration_seconds: number | null;
  cost_per_second_usd: number | null;
  credit_multiplier: number;
}

export interface ModelMargin {
  slug: string;
  display_name: string | null;
  seconds_per_scene: number;
  platform_cost_usd: number;
  user_price_usd: number;
  margin_usd: number;
  margin_percent: number | null;
  is_profitable: boolean;
}

export interface UserAdmin {
  id: string;
  email: string;
  full_name: string | null;
  company_name: string | null;
  country: string | null;
  industry: string | null;
  is_active: boolean;
  is_admin: boolean;
  onboarding_completed: boolean;
  created_at: string;
}

export interface FeatureFlagAdmin {
  key: string;
  description: string | null;
  is_enabled: boolean;
  applies_to: string;
}

export interface AlertEntry {
  event_type: string;
  label: string;
  count: number;
  threshold: number;
  window_minutes: number;
}

export interface SecurityEventEntry {
  id: string;
  event_type: string;
  severity: string;
  ip_address: string | null;
  description: string | null;
  created_at: string;
}

export interface AuditEntry {
  id: string;
  actor_email: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  detail: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface VideoModelCreate {
  slug: string;
  display_name: string;
  provider: string;
  model_id: string;
  max_duration_seconds: number;
  supported_resolutions: string[];
  supported_aspect_ratios: string[];
  supports_audio: boolean;
  supports_image_reference: boolean;
  cost_per_second_usd: number;
  credit_multiplier: number;
  quality_tier: string;
}

export const adminApi = {
  // pricing
  getRatio: () => api.get<{ usd_per_credit: number }>("/admin/pricing/ratio"),
  setRatio: (usdPerCredit: number) =>
    api.put<{ usd_per_credit: number }>("/admin/pricing/ratio", {
      usd_per_credit: usdPerCredit,
    }),
  listActionPricing: () => api.get<ActionPricing[]>("/admin/pricing/actions"),
  updateActionPricing: (
    actionKey: string,
    patch: { base_credits?: number; is_enabled?: boolean; notes?: string }
  ) => api.patch<ActionPricing>(`/admin/pricing/actions/${actionKey}`, patch),

  // models
  listModels: () => api.get<VideoModelAdmin[]>("/admin/models"),
  createModel: (body: VideoModelCreate) =>
    api.post<VideoModelAdmin>("/admin/models", body),
  updateModel: (
    slug: string,
    patch: {
      display_name?: string;
      credit_multiplier?: number;
      cost_per_second_usd?: number;
      is_enabled?: boolean;
      quality_tier?: string;
    }
  ) => api.patch<VideoModelAdmin>(`/admin/models/${slug}`, patch),
  margins: (secondsPerScene = 6) =>
    api.get<ModelMargin[]>(`/admin/models/margins?seconds_per_scene=${secondsPerScene}`),

  // plans & packages
  upsertPlan: (slug: string, body: Record<string, unknown>) =>
    api.put<{ slug: string; status: string }>(`/admin/plans/${slug}`, body),
  upsertPackage: (slug: string, body: Record<string, unknown>) =>
    api.put<{ slug: string; status: string }>(`/admin/packages/${slug}`, body),

  // users
  listUsers: (limit = 50) => api.get<UserAdmin[]>(`/admin/users?limit=${limit}`),
  setUserStatus: (userId: string, isActive: boolean) =>
    api.patch<UserAdmin>(`/admin/users/${userId}/status`, { is_active: isActive }),
  grantCredits: (userId: string, amount: number, reason: string) =>
    api.post<{ balance_credits: number }>(`/admin/users/${userId}/credits`, {
      amount,
      reason,
    }),

  // security & audit
  alerts: () => api.get<AlertEntry[]>("/admin/alerts"),
  securityEvents: (limit = 100) =>
    api.get<SecurityEventEntry[]>(`/admin/security-events?limit=${limit}`),
  auditLog: (limit = 100) => api.get<AuditEntry[]>(`/admin/audit-log?limit=${limit}`),

  // feature flags
  listFlags: () => api.get<FeatureFlagAdmin[]>("/admin/features"),
  updateFlag: (key: string, isEnabled: boolean, appliesTo?: string) =>
    api.patch<FeatureFlagAdmin>(`/admin/features/${key}`, {
      is_enabled: isEnabled,
      applies_to: appliesTo ?? null,
    }),
};
