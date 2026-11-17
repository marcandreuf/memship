import { apiClient } from "@/lib/client-api";

export interface RegistrationMemberInfo {
  id: number;
  member_number: string | null;
  first_name: string;
  last_name: string;
  email: string | null;
}

export interface RegistrationData {
  id: number;
  activity_id: number;
  party_id: number;
  modality_id: number | null;
  price_id: number | null;
  discount_code_id: number | null;
  status: string;
  original_amount: number | null;
  discounted_amount: number | null;
  vat_rate: number;
  /** Tax-inclusive — matches the invoice. Null for a free registration. */
  total_amount: number | null;
  registration_data: Record<string, unknown>;
  member_notes: string | null;
  admin_notes: string | null;
  cancelled_at: string | null;
  cancelled_reason: string | null;
  cancelled_by_name: string | null;
  /** `payment_expired` when the seat was released unpaid by the deadline sweep. */
  cancelled_cause: string | null;
  /** When an unpaid pending seat is released; null without auto-cancel. */
  payment_due_at: string | null;
  late_payment_at: string | null;
  late_payment_seen_at: string | null;
  refund_status: RefundStatus;
  receipt_id: number | null;
  receipt_status: string | null;
  receipt_due_date: string | null;
  created_at: string;
  member?: RegistrationMemberInfo;
}

export type RefundStatus = "none" | "due" | "returned";

export interface RegistrationPageMeta {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

export interface PaginatedRegistrations {
  items: RegistrationData[];
  meta: RegistrationPageMeta;
}

export interface EligibilityReason {
  code: string;
  min_age: number | null;
  max_age: number | null;
}

export interface EligibilityData {
  eligible: boolean;
  /** English, as the API states it; `details` is what the UI shows. */
  reasons: string[];
  details: EligibilityReason[];
}

export interface ConsentAcceptanceParam {
  activity_consent_id: number;
  accepted: boolean;
}

export interface RegisterParams {
  activityId: number;
  price_id: number;
  modality_id?: number;
  discount_code?: string;
  consents?: ConsentAcceptanceParam[];
  registration_data?: Record<string, unknown>;
  member_notes?: string;
}

export async function registerForActivity({
  activityId,
  ...data
}: RegisterParams): Promise<RegistrationData> {
  return apiClient(`/activities/${activityId}/register`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function checkEligibility(activityId: number): Promise<EligibilityData> {
  return apiClient(`/activities/${activityId}/eligibility`);
}

export async function cancelRegistration(registrationId: number, reason?: string): Promise<void> {
  await apiClient(`/registrations/${registrationId}`, {
    method: "DELETE",
    ...(reason ? { body: JSON.stringify({ reason }) } : {}),
  });
}

export async function changeRegistrationStatus(
  registrationId: number,
  status: string,
  admin_notes?: string,
  keep_payment?: boolean,
): Promise<RegistrationData> {
  return apiClient(`/registrations/${registrationId}/status`, {
    method: "PUT",
    body: JSON.stringify({ status, admin_notes, keep_payment }),
  });
}

export async function confirmWithoutPayment(registrationId: number): Promise<RegistrationData> {
  return apiClient(`/registrations/${registrationId}/confirm-without-payment`, {
    method: "POST",
  });
}

export interface RefundData {
  registration_id: number;
  activity_id: number;
  activity_name: string;
  member_name: string | null;
  member_number: string | null;
  cancelled_at: string | null;
  refund_status: RefundStatus;
  receipt_id: number;
  receipt_number: string;
  amount: number;
  payment_method: string | null;
  payment_date: string | null;
  /** What finds the payment in the gateway's dashboard. */
  gateway_reference: string | null;
  refund_returned_at: string | null;
  refund_credit_note_id: number | null;
}

export async function listRefunds(params: {
  page?: number;
  per_page?: number;
  refund_status?: "due" | "returned";
}): Promise<{ items: RefundData[]; meta: RegistrationPageMeta }> {
  const sp = new URLSearchParams();
  if (params.page) sp.set("page", String(params.page));
  if (params.per_page) sp.set("per_page", String(params.per_page));
  if (params.refund_status) sp.set("refund_status", params.refund_status);
  const qs = sp.toString();
  return apiClient(`/registrations/refunds${qs ? `?${qs}` : ""}`);
}

export async function markRefundReturned(registrationId: number): Promise<RefundData> {
  return apiClient(`/registrations/${registrationId}/refund-returned`, { method: "POST" });
}

export interface LatePaymentData {
  registration_id: number;
  activity_id: number;
  activity_name: string;
  member_name: string | null;
  status: string;
  refund_status: RefundStatus;
  late_payment_at: string;
}

export async function listUnseenLatePayments(): Promise<{ items: LatePaymentData[] }> {
  return apiClient("/registrations/late-payments");
}

export async function acknowledgeLatePayment(registrationId: number): Promise<void> {
  await apiClient(`/registrations/${registrationId}/late-payment-seen`, { method: "POST" });
}

export interface ListRegistrationsParams {
  activityId: number;
  page?: number;
  per_page?: number;
  status?: string;
}

export async function listActivityRegistrations(
  params: ListRegistrationsParams
): Promise<PaginatedRegistrations> {
  const sp = new URLSearchParams();
  if (params.page) sp.set("page", String(params.page));
  if (params.per_page) sp.set("per_page", String(params.per_page));
  if (params.status) sp.set("status", params.status);
  const qs = sp.toString();
  return apiClient(`/activities/${params.activityId}/registrations${qs ? `?${qs}` : ""}`);
}

export interface RegistrationAttachmentData {
  id: number;
  registration_id: number;
  attachment_type_id: number | null;
  file_name: string;
  file_size: number | null;
  mime_type: string | null;
  uploaded_at: string | null;
}

export async function listRegistrationAttachments(registrationId: number): Promise<RegistrationAttachmentData[]> {
  return apiClient(`/registrations/${registrationId}/attachments`);
}

export async function uploadRegistrationAttachment(
  registrationId: number,
  file: File,
  attachmentTypeId?: number,
): Promise<RegistrationAttachmentData> {
  const formData = new FormData();
  formData.append("file", file);
  const qs = attachmentTypeId ? `?attachment_type_id=${attachmentTypeId}` : "";
  const res = await fetch(`/api/registrations/${registrationId}/attachments${qs}`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || "Upload failed");
  }
  return res.json();
}

export interface RegistrationStats {
  confirmed: number;
  waitlist: number;
  cancelled: number;
  pending: number;
  total: number;
}

export async function getRegistrationStats(): Promise<RegistrationStats> {
  return apiClient("/registrations/stats");
}

export async function listMyRegistrations(params: {
  page?: number;
  per_page?: number;
  upcoming?: boolean;
} = {}): Promise<PaginatedRegistrations> {
  const sp = new URLSearchParams();
  if (params.page) sp.set("page", String(params.page));
  if (params.per_page) sp.set("per_page", String(params.per_page));
  if (params.upcoming) sp.set("upcoming", "true");
  const qs = sp.toString();
  return apiClient(`/members/me/registrations${qs ? `?${qs}` : ""}`);
}
