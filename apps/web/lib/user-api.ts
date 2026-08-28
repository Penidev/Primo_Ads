import { api } from "./api";
import type { UserProfile } from "@/types/auth";

export interface OnboardingUpdate {
  full_name?: string;
  company_name?: string;
  country?: string;
  industry?: string;
  company_size?: string;
  role?: string;
  use_case?: string;
  ad_platforms?: string[];
  complete?: boolean;
}

export const userApi = {
  updateOnboarding: (data: OnboardingUpdate) =>
    api.patch<UserProfile>("/users/me/onboarding", data),
};
