import { apiClient } from "@/lib/client-api";

export interface MandateData {
  id: number;
  member_id: number;
  mandate_reference: string;
  creditor_id: string;
  debtor_name: string;
  debtor_iban: string;
  debtor_bic: string | null;
  mandate_type: string;
  signature_method: string;
  status: string;
  signed_at: string;
  document_path: string | null;
  cancelled_at: string | null;
  notes: string | null;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
  // Joined fields from backend
  member_name?: string;
  member_number?: string;
}

export interface PaginatedMandates {
  items: MandateData[];
  meta: {
    page: number;
    per_page: number;
    total: number;
    total_pages: number;
  };
}

export async function getMandates(params?: URLSearchParams): Promise<PaginatedMandates> {
  return apiClient(`/mandates${params ? `?${params}` : ""}`);
}

export async function getMandate(id: number): Promise<MandateData> {
  return apiClient(`/mandates/${id}`);
}

export async function createMandate(data: Record<string, unknown>): Promise<MandateData> {
  return apiClient("/mandates", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateMandate(id: number, data: Record<string, unknown>): Promise<MandateData> {
  return apiClient(`/mandates/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function cancelMandate(id: number): Promise<MandateData> {
  return apiClient(`/mandates/${id}/cancel`, { method: "POST" });
}

export async function uploadSignedMandate(id: number, file: File): Promise<MandateData> {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient(`/mandates/${id}/upload-signed`, {
    method: "POST",
    headers: {},
    body: formData,
  });
}
