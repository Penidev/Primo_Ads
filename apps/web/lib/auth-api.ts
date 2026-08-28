import { api } from "./api";
import type { TokenResponse, UserProfile } from "@/types/auth";

export const authApi = {
  register: (email: string, password: string, full_name?: string) =>
    api.post<UserProfile>("/auth/register", { email, password, full_name }),

  login: (email: string, password: string, mfaCode?: string) =>
    api.post<TokenResponse>("/auth/login", {
      email,
      password,
      mfa_code: mfaCode ?? null,
    }),

  logout: () => api.post<void>("/auth/logout"),

  me: () => api.get<UserProfile>("/auth/me"),

  refresh: () => api.post<TokenResponse>("/auth/refresh"),

  requestPasswordReset: (email: string) =>
    api.post<{ detail: string }>("/auth/password-reset", { email }),

  confirmPasswordReset: (token: string, newPassword: string) =>
    api.post<void>("/auth/password-reset/confirm", {
      token,
      new_password: newPassword,
    }),
};
