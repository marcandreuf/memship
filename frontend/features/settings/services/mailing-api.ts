import { apiClient } from "@/lib/client-api";

export type MailProvider = "resend" | "gmail";

export interface MailSecretStatus {
  configured: boolean;
  last4: string | null;
}

export interface MailResendView {
  from_email: string;
  api_key: MailSecretStatus;
  ready: boolean;
}

export interface MailGmailView {
  user: string;
  from_email: string;
  app_password: MailSecretStatus;
  ready: boolean;
}

export interface MailingConfigView {
  active_provider: MailProvider | null;
  resend: MailResendView;
  gmail: MailGmailView;
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

export interface MailGmailUpdate {
  user?: string;
  from_email?: string;
  app_password?: MailSecretUpdate;
}

export interface MailingConfigUpdate {
  active_provider?: MailProvider | null;
  resend?: MailResendUpdate;
  gmail?: MailGmailUpdate;
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