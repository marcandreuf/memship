import { apiClient } from "@/lib/client-api";

export interface ReceiptData {
  id: number;
  receipt_number: string;
  member_id: number;
  concept_id: number | null;
  registration_id: number | null;
  remittance_id: number | null;
  origin: string;
  description: string;
  base_amount: number;
  vat_rate: number;
  vat_amount: number;
  total_amount: number;
  discount_amount: number | null;
  discount_type: string | null;
  status: string;
  payment_method: string | null;
  emission_date: string;
  due_date: string | null;
  payment_date: string | null;
  return_date: string | null;
  return_reason: string | null;
  is_batchable: boolean;
  transaction_id: string | null;
  billing_period_start: string | null;
  billing_period_end: string | null;
  notes: string | null;
  created_by: number | null;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
  // Detail fields
  member_name?: string | null;
  member_number?: string | null;
  concept_name?: string | null;
}

export interface ConceptData {
  id: number;
  name: string;
  code: string | null;
  description: string | null;
  concept_type: string;
  default_amount: number;
  vat_rate: number;
  default_discount: number | null;
  default_discount_type: string | null;
  accounting_code: string | null;
  is_active: boolean;
}

export interface PaginatedReceipts {
  items: ReceiptData[];
  meta: {
    page: number;
    per_page: number;
    total: number;
    total_pages: number;
  };
}

export async function getReceipts(params?: URLSearchParams): Promise<PaginatedReceipts> {
  return apiClient(`/receipts${params ? `?${params}` : ""}`);
}

export async function getReceipt(id: number): Promise<ReceiptData> {
  return apiClient(`/receipts/${id}`);
}

export async function createReceipt(data: Record<string, unknown>): Promise<ReceiptData> {
  return apiClient("/receipts", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateReceipt(id: number, data: Record<string, unknown>): Promise<ReceiptData> {
  return apiClient(`/receipts/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function emitReceipt(id: number): Promise<ReceiptData> {
  return apiClient(`/receipts/${id}/emit`, { method: "POST" });
}

export async function payReceipt(id: number, data: { payment_method: string; payment_date?: string }): Promise<ReceiptData> {
  return apiClient(`/receipts/${id}/pay`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function cancelReceipt(id: number): Promise<ReceiptData> {
  return apiClient(`/receipts/${id}/cancel`, { method: "POST" });
}

export async function returnReceipt(id: number, data: { return_reason: string; return_date?: string }): Promise<ReceiptData> {
  return apiClient(`/receipts/${id}/return`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function reemitReceipt(id: number): Promise<ReceiptData> {
  return apiClient(`/receipts/${id}/reemit`, { method: "POST" });
}

export async function generateMembershipFees(data: Record<string, unknown>): Promise<{ generated: number; receipt_ids: number[] }> {
  return apiClient("/receipts/generate-membership-fees", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getConcepts(type?: string): Promise<ConceptData[]> {
  const params = type ? `?concept_type=${type}` : "";
  return apiClient(`/concepts${params}`);
}

export interface ReceiptStats {
  new: number;
  pending: number;
  emitted: number;
  paid: number;
  returned: number;
  cancelled: number;
  overdue: number;
  pending_amount: number;
  paid_this_month: number;
  overdue_amount: number;
}

export async function getReceiptStats(): Promise<ReceiptStats> {
  return apiClient("/receipts/stats");
}

export async function getMyReceipts(params?: URLSearchParams): Promise<PaginatedReceipts> {
  return apiClient(`/members/me/receipts${params ? `?${params}` : ""}`);
}

export async function createConcept(data: Record<string, unknown>): Promise<ConceptData> {
  return apiClient("/concepts", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// --- Stripe Checkout ---

export interface StripeCheckoutResponse {
  redirect_url: string;
  session_id: string;
}

export async function createStripeCheckout(receiptId: number): Promise<StripeCheckoutResponse> {
  return apiClient(`/receipts/${receiptId}/stripe/checkout`, {
    method: "POST",
  });
}

export async function getReceiptByStripeSession(sessionId: string): Promise<ReceiptData> {
  return apiClient(`/receipts/by-stripe-session/${sessionId}`);
}
