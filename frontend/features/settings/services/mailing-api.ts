import { apiClient } from "@/lib/client-api";

export type MailProvider = "resend" | "smtp";

export interface MailSecretStatus {
  configured: boolean;
  last4: string | null;
}

export type MailHealthStatus = "unverified" | "ok" | "failing";

export interface MailHealth {
  status: MailHealthStatus;
  last_success_at: string | null;
  last_failure_at: string | null;
  last_failure: string | null;
}

export interface MailResendView {
  from_email: string;
  api_key: MailSecretStatus;
  ready: boolean;
  health: MailHealth;
}

export interface MailSmtpView {
  host: string;
  port: number;
  tls: boolean;
  user: string;
  from_email: string;
  password: MailSecretStatus;
  ready: boolean;
  health: MailHealth;
}

export interface MailingConfigView {
  active_provider: MailProvider | null;
  resend: MailResendView;
  smtp: MailSmtpView;
  secrets_encryption_available: boolean;
  sources: Record<string, string>;
}

export interface MailSecretUpdate {
  value?: string;
  clear?: boolean;
  secret?: boolean;
}

export interface MailResendUpdate {
  from_email?: string;
  api_key?: MailSecretUpdate;
}

export interface MailSmtpUpdate {
  host?: string;
  port?: number;
  tls?: boolean;
  user?: string;
  from_email?: string;
  password?: MailSecretUpdate;
}

export interface MailingConfigUpdate {
  active_provider?: MailProvider | null;
  resend?: MailResendUpdate;
  smtp?: MailSmtpUpdate;
}

export interface MailingTestResult {
  ok: boolean;
  error: string | null;
}

export async function getMailingConfig(): Promise<MailingConfigView> {
  return apiClient("/settings/mailing");
}

export async function updateMailingConfig(
  data: MailingConfigUpdate
): Promise<MailingConfigView> {
  return apiClient("/settings/mailing", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function testMailingProvider(
  provider: MailProvider
): Promise<MailingTestResult> {
  return apiClient("/settings/mailing/test", {
    method: "POST",
    body: JSON.stringify({ provider }),
  });
}