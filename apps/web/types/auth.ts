export interface UserProfile {
  id: string;
  email: string;
  full_name: string | null;
  company_name?: string | null;
  country?: string | null;
  industry?: string | null;
  company_size?: string | null;
  role?: string | null;
  use_case?: string | null;
  ad_platforms?: string[] | null;
  is_admin: boolean;
  onboarding_completed: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}
