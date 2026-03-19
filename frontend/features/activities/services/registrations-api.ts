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
  member_id: number;
  modality_id: number | null;
  price_id: number | null;
  discount_code_id: number | null;
  status: string;
  original_amount: number | null;
  discounted_amount: number | null;
  registration_data: Record<string, unknown>;
  member_notes: string | null;
  admin_notes: string | null;
  cancelled_at: string | null;
  cancelled_reason: string | null;
  cancelled_by_name: string | null;
  created_at: string;
  member?: RegistrationMemberInfo;
}

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

export interface EligibilityData {
  eligible: boolean;
  reasons: string[];
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
  admin_notes?: string
): Promise<RegistrationData> {
  return apiClient(`/registrations/${registrationId}/status`, {
    method: "PUT",
    body: JSON.stringify({ status, admin_notes }),
  });
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

export async function listMyRegistrations(params: {
  page?: number;
  per_page?: number;
} = {}): Promise<PaginatedRegistrations> {
  const sp = new URLSearchParams();
  if (params.page) sp.set("page", String(params.page));
  if (params.per_page) sp.set("per_page", String(params.per_page));
  const qs = sp.toString();
  return apiClient(`/members/me/registrations${qs ? `?${qs}` : ""}`);
}
