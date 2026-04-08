import { apiClient } from "@/lib/client-api";
import type { ReceiptData } from "@/features/receipts/services/receipts-api";

export interface RemittanceData {
  id: number;
  remittance_number: string;
  remittance_type: string;
  status: string;
  emission_date: string;
  due_date: string;
  total_amount: number;
  receipt_count: number;
  sepa_file_path: string | null;
  creditor_name: string;
  creditor_iban: string;
  creditor_bic: string | null;
  creditor_id: string;
  notes: string | null;
  created_by: number | null;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
  receipts?: ReceiptData[];
}

export interface PaginatedRemittances {
  items: RemittanceData[];
  meta: {
    page: number;
    per_page: number;
    total: number;
    total_pages: number;
  };
}

export interface ImportReturnResult {
  processed: number;
  returned: number;
  not_found: number;
}

export async function getRemittances(params?: URLSearchParams): Promise<PaginatedRemittances> {
  return apiClient(`/remittances${params ? `?${params}` : ""}`);
}

export async function getRemittance(id: number): Promise<RemittanceData> {
  return apiClient(`/remittances/${id}`);
}

export async function createRemittance(data: { receipt_ids: number[]; due_date: string; notes?: string }): Promise<RemittanceData> {
  return apiClient("/remittances", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function generateRemittanceXml(id: number): Promise<RemittanceData> {
  return apiClient(`/remittances/${id}/generate-xml`, { method: "POST" });
}

export async function markRemittanceSubmitted(id: number): Promise<RemittanceData> {
  return apiClient(`/remittances/${id}/mark-submitted`, { method: "POST" });
}

export async function importRemittanceReturns(id: number, data: Array<{ receipt_number: string; reason: string }>): Promise<ImportReturnResult> {
  return apiClient(`/remittances/${id}/import-returns`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function closeRemittance(id: number): Promise<RemittanceData> {
  return apiClient(`/remittances/${id}/close`, { method: "POST" });
}

export async function cancelRemittance(id: number): Promise<RemittanceData> {
  return apiClient(`/remittances/${id}/cancel`, { method: "POST" });
}

export async function getRemittanceStats(id: number): Promise<Record<string, number>> {
  return apiClient(`/remittances/${id}/stats`);
}
