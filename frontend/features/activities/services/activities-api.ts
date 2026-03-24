import { apiClient } from "@/lib/client-api";

export interface ActivityModalityData {
  id: number;
  activity_id: number;
  name: string;
  description: string | null;
  max_participants: number | null;
  current_participants: number;
  registration_deadline: string | null;
  display_order: number;
  is_active: boolean;
  created_at: string;
}

export interface ActivityPriceData {
  id: number;
  activity_id: number;
  modality_id: number | null;
  name: string;
  description: string | null;
  amount: number;
  display_order: number;
  is_optional: boolean;
  is_default: boolean;
  is_visible: boolean;
  max_registrations: number | null;
  current_registrations: number;
  valid_from: string | null;
  valid_until: string | null;
  is_active: boolean;
  created_at: string;
}

export interface ActivityData {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  short_description: string | null;
  starts_at: string;
  ends_at: string;
  location: string | null;
  location_details: string | null;
  location_url: string | null;
  registration_starts_at: string;
  registration_ends_at: string;
  min_participants: number;
  max_participants: number;
  current_participants: number;
  waitlist_count: number;
  available_spots: number;
  is_registration_open: boolean;
  min_age: number | null;
  max_age: number | null;
  allowed_membership_types: number[] | null;
  image_url: string | null;
  status: string;
  tax_rate: number;
  features: Record<string, unknown>;
  requirements: string | null;
  what_to_bring: string | null;
  cancellation_policy: string | null;
  allow_self_cancellation: boolean;
  self_cancellation_deadline_hours: number | null;
  is_active: boolean;
  is_featured: boolean;
  created_by: number | null;
  created_at: string;
  updated_at: string;
  modalities: ActivityModalityData[];
  prices: ActivityPriceData[];
}

export interface ActivityListData {
  id: number;
  name: string;
  slug: string;
  short_description: string | null;
  starts_at: string;
  ends_at: string;
  location: string | null;
  max_participants: number;
  current_participants: number;
  registration_starts_at: string;
  registration_ends_at: string;
  available_spots: number;
  is_registration_open: boolean;
  status: string;
  image_url: string | null;
  is_featured: boolean;
  created_at: string;
}

export interface PageMeta {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

export interface PaginatedActivities {
  items: ActivityListData[];
  meta: PageMeta;
}

export interface ListActivitiesParams {
  page?: number;
  per_page?: number;
  search?: string;
  status?: string;
}

// Activities
export async function listActivities(params: ListActivitiesParams = {}): Promise<PaginatedActivities> {
  const sp = new URLSearchParams();
  if (params.page) sp.set("page", String(params.page));
  if (params.per_page) sp.set("per_page", String(params.per_page));
  if (params.search) sp.set("search", params.search);
  if (params.status) sp.set("status", params.status);
  const qs = sp.toString();
  return apiClient(`/activities${qs ? `?${qs}` : ""}`);
}

export async function getActivity(id: number): Promise<ActivityData> {
  return apiClient(`/activities/${id}`);
}

export async function createActivity(data: Record<string, unknown>): Promise<ActivityData> {
  return apiClient("/activities", { method: "POST", body: JSON.stringify(data) });
}

export async function updateActivity(id: number, data: Record<string, unknown>): Promise<ActivityData> {
  return apiClient(`/activities/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function deleteActivity(id: number): Promise<void> {
  await apiClient(`/activities/${id}`, { method: "DELETE" });
}

export async function publishActivity(id: number): Promise<ActivityData> {
  return apiClient(`/activities/${id}/publish`, { method: "PUT" });
}

export async function archiveActivity(id: number): Promise<ActivityData> {
  return apiClient(`/activities/${id}/archive`, { method: "PUT" });
}

export async function cancelActivity(id: number): Promise<ActivityData> {
  return apiClient(`/activities/${id}/cancel`, { method: "PUT" });
}

// Modalities
export async function listModalities(activityId: number): Promise<ActivityModalityData[]> {
  return apiClient(`/activities/${activityId}/modalities`);
}

export async function createModality(activityId: number, data: Record<string, unknown>): Promise<ActivityModalityData> {
  return apiClient(`/activities/${activityId}/modalities`, { method: "POST", body: JSON.stringify(data) });
}

export async function updateModality(activityId: number, modalityId: number, data: Record<string, unknown>): Promise<ActivityModalityData> {
  return apiClient(`/activities/${activityId}/modalities/${modalityId}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function deleteModality(activityId: number, modalityId: number): Promise<void> {
  await apiClient(`/activities/${activityId}/modalities/${modalityId}`, { method: "DELETE" });
}

// Prices
export async function listPrices(activityId: number): Promise<ActivityPriceData[]> {
  return apiClient(`/activities/${activityId}/prices`);
}

export async function createPrice(activityId: number, data: Record<string, unknown>): Promise<ActivityPriceData> {
  return apiClient(`/activities/${activityId}/prices`, { method: "POST", body: JSON.stringify(data) });
}

export async function updatePrice(activityId: number, priceId: number, data: Record<string, unknown>): Promise<ActivityPriceData> {
  return apiClient(`/activities/${activityId}/prices/${priceId}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function deletePrice(activityId: number, priceId: number): Promise<void> {
  await apiClient(`/activities/${activityId}/prices/${priceId}`, { method: "DELETE" });
}

// Discount Codes
export interface DiscountCodeData {
  id: number;
  activity_id: number;
  code: string;
  description: string | null;
  discount_type: string;
  discount_value: number;
  max_uses: number | null;
  current_uses: number;
  valid_from: string | null;
  valid_until: string | null;
  is_active: boolean;
  created_at: string;
}

export interface ValidateDiscountResult {
  valid: boolean;
  discount_type: string | null;
  discount_value: number | null;
  original_amount: number | null;
  discounted_amount: number | null;
  error: string | null;
}

export async function listDiscountCodes(activityId: number): Promise<DiscountCodeData[]> {
  return apiClient(`/activities/${activityId}/discount-codes`);
}

export async function createDiscountCode(activityId: number, data: Record<string, unknown>): Promise<DiscountCodeData> {
  return apiClient(`/activities/${activityId}/discount-codes`, { method: "POST", body: JSON.stringify(data) });
}

export async function updateDiscountCode(activityId: number, codeId: number, data: Record<string, unknown>): Promise<DiscountCodeData> {
  return apiClient(`/activities/${activityId}/discount-codes/${codeId}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function deleteDiscountCode(activityId: number, codeId: number): Promise<void> {
  await apiClient(`/activities/${activityId}/discount-codes/${codeId}`, { method: "DELETE" });
}

export async function validateDiscount(activityId: number, code: string, priceId?: number): Promise<ValidateDiscountResult> {
  const qs = priceId ? `?price_id=${priceId}` : "";
  return apiClient(`/activities/${activityId}/validate-discount${qs}`, { method: "POST", body: JSON.stringify({ code }) });
}

// Activity Consents
export interface ActivityConsentData {
  id: number;
  activity_id: number;
  title: string;
  content: string;
  is_mandatory: boolean;
  display_order: number;
  is_active: boolean;
  created_at: string;
}

export async function listConsents(activityId: number): Promise<ActivityConsentData[]> {
  return apiClient(`/activities/${activityId}/consents`);
}

export async function createConsent(activityId: number, data: Record<string, unknown>): Promise<ActivityConsentData> {
  return apiClient(`/activities/${activityId}/consents`, { method: "POST", body: JSON.stringify(data) });
}

export async function updateConsent(activityId: number, consentId: number, data: Record<string, unknown>): Promise<ActivityConsentData> {
  return apiClient(`/activities/${activityId}/consents/${consentId}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function deleteConsent(activityId: number, consentId: number): Promise<void> {
  await apiClient(`/activities/${activityId}/consents/${consentId}`, { method: "DELETE" });
}

// Activity Attachment Types
export interface ActivityAttachmentTypeData {
  id: number;
  activity_id: number;
  name: string;
  description: string | null;
  allowed_extensions: string[];
  max_file_size_mb: number;
  is_mandatory: boolean;
  display_order: number;
  is_active: boolean;
  created_at: string;
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

export async function listAttachmentTypes(activityId: number): Promise<ActivityAttachmentTypeData[]> {
  return apiClient(`/activities/${activityId}/attachment-types`);
}

export async function createAttachmentType(activityId: number, data: Record<string, unknown>): Promise<ActivityAttachmentTypeData> {
  return apiClient(`/activities/${activityId}/attachment-types`, { method: "POST", body: JSON.stringify(data) });
}

export async function updateAttachmentType(activityId: number, typeId: number, data: Record<string, unknown>): Promise<ActivityAttachmentTypeData> {
  return apiClient(`/activities/${activityId}/attachment-types/${typeId}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function deleteAttachmentType(activityId: number, typeId: number): Promise<void> {
  await apiClient(`/activities/${activityId}/attachment-types/${typeId}`, { method: "DELETE" });
}

// Cover Image
export async function uploadCoverImage(activityId: number, file: File): Promise<{ image_url: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`/api/activities/${activityId}/cover-image`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(typeof err.detail === "string" ? err.detail : "Upload failed");
  }
  return res.json();
}

export async function deleteCoverImage(activityId: number): Promise<void> {
  await apiClient(`/activities/${activityId}/cover-image`, { method: "DELETE" });
}
