import { api } from "./api";

export interface MfaStatus {
  mfa_enabled: boolean;
  mfa_required: boolean;
  recovery_codes_remaining: number;
}

export interface MfaSetup {
  secret: string;
  provisioning_uri: string;
}

export interface MfaActivation {
  recovery_codes: string[];
}

export const mfaApi = {
  status: () => api.get<MfaStatus>("/mfa"),
  beginSetup: () => api.post<MfaSetup>("/mfa/setup"),
  activate: (code: string) => api.post<MfaActivation>("/mfa/activate", { code }),
  disable: (password: string, code: string) =>
    api.post<void>("/mfa/disable", { password, code }),
};
