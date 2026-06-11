import { apiClient } from "@/lib/client-api";

export type BillingFrequency = "monthly" | "quarterly" | "annual";

export interface BillingRunError {
  member_id?: number;
  message?: string;
  [key: string]: unknown;
}

export interface BillingRun {
  id: number;
  frequency: string;
  period_start: string;
  period_end: string;
  triggered_by: string;
  triggered_by_user_id: number | null;
  status: string;
  receipts_generated: number;
  errors: BillingRunError[];
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface BillingRunListResponse {
  items: BillingRun[];
  meta: { page: number; per_page: number; total: number; total_pages: number };
}

export interface RunNowResponse {
  runs: BillingRun[];
  receipts_generated: number;
}

export interface BillingRunFilters {
  page?: number;
  per_page?: number;
  frequency?: string;
  status?: string;
}

export async function getBillingRuns(
  filters: BillingRunFilters = {}
): Promise<BillingRunListResponse> {
  const params = new URLSearchParams();
  if (filters.page) params.set("page", String(filters.page));
  if (filters.per_page) params.set("per_page", String(filters.per_page));
  if (filters.frequency) params.set("frequency", filters.frequency);
  if (filters.status) params.set("status", filters.status);
  const query = params.toString();
  return apiClient(`/billing-runs${query ? `?${query}` : ""}`);
}

export async function getBillingRun(id: number): Promise<BillingRun> {
  return apiClient(`/billing-runs/${id}`);
}

export async function runBillingNow(
  frequency?: BillingFrequency
): Promise<RunNowResponse> {
  return apiClient("/billing-runs/run-now", {
    method: "POST",
    body: JSON.stringify(frequency ? { frequency } : {}),
  });
}
