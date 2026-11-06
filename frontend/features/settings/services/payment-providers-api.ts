import { apiClient } from "@/lib/client-api";

export interface ProviderField {
  key: string;
  label: string;
  type: "text" | "password" | "select" | "checkbox";
  placeholder?: string;
  options?: string[];
  required?: boolean;
}

export interface ProviderTypeSchema {
  provider_type: string;
  fields: ProviderField[];
  sensitive_fields: string[];
  available: boolean;
  /** Where the gateway must send its notifications; null when it is told per payment. */
  webhook_url: string | null;
  webhook_events: string[];
}

export interface PaymentProvider {
  id: number;
  provider_type: string;
  display_name: string;
  status: string;
  config: Record<string, string>;
  is_default: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface PaymentProviderListResponse {
  items: PaymentProvider[];
  meta: { page: number; per_page: number; total: number; total_pages: number };
}

/** A validation failure as a code plus its parameters, for the UI to translate. */
export interface ProviderConfigError {
  code: string;
  field?: string;
  prefix?: string;
  length?: number;
  min?: number;
  max?: number;
  options?: string[];
  provider_type?: string;
}

export interface TestResult {
  success: boolean;
  errors: ProviderConfigError[];
  /** Text only the provider could produce (a live API's own words). Not translatable. */
  message: string | null;
}

export async function getPaymentProviders(): Promise<PaymentProviderListResponse> {
  return apiClient("/payment-providers");
}

export type WebhookEventStatus = "received" | "processed" | "failed" | "ignored";

/** A recorded gateway notification. The payload is deliberately not returned. */
export interface WebhookEvent {
  id: number;
  provider_type: string;
  external_event_id: string;
  event_type: string;
  status: WebhookEventStatus;
  error_message: string | null;
  receipt_id: number | null;
  receipt_number: string | null;
  created_at: string | null;
  processed_at: string | null;
}

export interface WebhookEventListResponse {
  items: WebhookEvent[];
  meta: { page: number; per_page: number; total: number; total_pages: number };
}

/** Notifications refused at the signature check; never recorded as events. */
export interface WebhookRejections {
  available: boolean;
  days: number;
  items: {
    provider_type: string;
    count: number;
    last_at: string | null;
    last_reason: string | null;
  }[];
}

export async function getWebhookRejections(): Promise<WebhookRejections> {
  return apiClient("/payment-providers/webhook-rejections");
}

export async function getWebhookEvents(
  statuses: WebhookEventStatus[],
  page: number
): Promise<WebhookEventListResponse> {
  const params = new URLSearchParams({ page: String(page) });
  for (const s of statuses) params.append("status", s);
  return apiClient(`/payment-providers/webhook-events?${params}`);
}

export interface ActivePaymentMethod {
  provider_type: string;
  status: string;
  // The methods a member may choose for this provider. Redsys reports `bizum`
  // only where the administrator has confirmed the bank enabled it (#405), so
  // the pay buttons come from here rather than from the provider type.
  methods: string[];
}

export async function getActivePaymentMethods(): Promise<ActivePaymentMethod[]> {
  return apiClient("/payment-providers/active-methods");
}

export async function getPaymentProvider(id: number): Promise<PaymentProvider> {
  return apiClient(`/payment-providers/${id}`);
}

export async function createPaymentProvider(
  data: Partial<PaymentProvider>
): Promise<PaymentProvider> {
  return apiClient("/payment-providers", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updatePaymentProvider(
  id: number,
  data: Partial<PaymentProvider>
): Promise<PaymentProvider> {
  return apiClient(`/payment-providers/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deletePaymentProvider(id: number): Promise<void> {
  return apiClient(`/payment-providers/${id}`, { method: "DELETE" });
}

export async function togglePaymentProvider(
  id: number
): Promise<PaymentProvider> {
  return apiClient(`/payment-providers/${id}/toggle`, { method: "POST" });
}

export async function testPaymentProvider(id: number): Promise<TestResult> {
  return apiClient(`/payment-providers/${id}/test`, { method: "POST" });
}

export async function getProviderTypes(): Promise<ProviderTypeSchema[]> {
  return apiClient("/payment-providers/types");
}
