import { apiClient } from "@/lib/client-api";

export interface ProviderField {
  key: string;
  label: string;
  type: "text" | "password" | "select";
  placeholder?: string;
  options?: string[];
  required?: boolean;
}

export interface ProviderTypeSchema {
  provider_type: string;
  fields: ProviderField[];
  sensitive_fields: string[];
  available: boolean;
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

export interface TestResult {
  success: boolean;
  message: string;
}

export async function getPaymentProviders(): Promise<PaymentProviderListResponse> {
  return apiClient("/payment-providers");
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
