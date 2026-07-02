import { apiClient } from "@/lib/client-api";

export type TargetType = "all" | "group" | "membership_type";
export type AnnouncementStatus = "draft" | "sent";

export interface AnnouncementData {
  id: number;
  subject: string;
  body: string;
  target_type: TargetType;
  target_id: number | null;
  status: AnnouncementStatus;
  recipient_count: number | null;
  sent_at: string | null;
  created_by_user_id: number | null;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface PaginatedAnnouncements {
  items: AnnouncementData[];
  meta: { page: number; per_page: number; total: number; total_pages: number };
}

export interface AnnouncementFilters {
  page?: number;
  per_page?: number;
}

export interface AnnouncementInput {
  subject: string;
  body: string;
  target_type: TargetType;
  target_id?: number | null;
}

export async function getAnnouncements(
  filters: AnnouncementFilters = {}
): Promise<PaginatedAnnouncements> {
  const params = new URLSearchParams();
  if (filters.page) params.set("page", String(filters.page));
  if (filters.per_page) params.set("per_page", String(filters.per_page));
  const query = params.toString();
  return apiClient(`/announcements${query ? `?${query}` : ""}`);
}

export async function getAnnouncement(id: number): Promise<AnnouncementData> {
  return apiClient(`/announcements/${id}`);
}

export async function createAnnouncement(
  data: AnnouncementInput
): Promise<AnnouncementData> {
  return apiClient("/announcements", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAnnouncement(
  id: number,
  data: Partial<AnnouncementInput>
): Promise<AnnouncementData> {
  return apiClient(`/announcements/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function sendAnnouncement(id: number): Promise<AnnouncementData> {
  return apiClient(`/announcements/${id}/send`, { method: "POST" });
}

export async function getAudiencePreview(id: number): Promise<{ count: number }> {
  return apiClient(`/announcements/${id}/audience-preview`);
}

export interface RecipientData {
  member_id: number;
  name: string;
  email: string | null;
  emailed: boolean;
  in_app: boolean;
  seen_at: string | null;
}

export interface PaginatedRecipients {
  items: RecipientData[];
  meta: { page: number; per_page: number; total: number; total_pages: number };
}

export interface RecipientStats {
  recipient_count: number;
  emailed_count: number;
  seen_count: number;
  sent_by: string | null;
}

export async function getRecipients(
  id: number,
  page = 1,
  perPage = 20
): Promise<PaginatedRecipients> {
  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("per_page", String(perPage));
  return apiClient(`/announcements/${id}/recipients?${params.toString()}`);
}

export async function getRecipientStats(id: number): Promise<RecipientStats> {
  return apiClient(`/announcements/${id}/stats`);
}
