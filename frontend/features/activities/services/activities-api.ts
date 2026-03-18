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
  available_spots: number;
  is_registration_open: boolean;
  status: string;
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
