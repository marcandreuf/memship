import { apiClient } from "@/lib/client-api";

export interface SsoSecretStatus {
  configured: boolean;
  last4: string | null;
}

export interface SsoGoogleView {
  enabled: boolean;
  client_id: string;
  client_secret: SsoSecretStatus;
  ready: boolean;
}

export interface SsoAppleView {
  enabled: boolean;
  client_id: string;
  team_id: string;
  key_id: string;
  private_key: SsoSecretStatus;
  ready: boolean;
}

export interface SsoConfigView {
  google: SsoGoogleView;
  apple: SsoAppleView;
  backend_public_url: string;
  redirect_uris: Record<string, string>;
  secrets_encryption_available: boolean;
  sources: Record<string, string>;
}

export interface SsoSecretUpdate {
  value?: string;
  clear?: boolean;
  secret?: boolean;
}

export interface SsoGoogleUpdate {
  enabled?: boolean;
  client_id?: string;
  client_secret?: SsoSecretUpdate;
}

export interface SsoAppleUpdate {
  enabled?: boolean;
  client_id?: string;
  team_id?: string;
  key_id?: string;
  private_key?: SsoSecretUpdate;
}

export interface SsoConfigUpdate {
  google?: SsoGoogleUpdate;
  apple?: SsoAppleUpdate;
}

export async function getSsoConfig(): Promise<SsoConfigView> {
  return apiClient("/settings/sso");
}

export async function updateSsoConfig(
  data: SsoConfigUpdate
): Promise<SsoConfigView> {
  return apiClient("/settings/sso", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}