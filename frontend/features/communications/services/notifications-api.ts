import { apiClient } from "@/lib/client-api";
import type { AnnouncementData } from "./announcements-api";

export interface NotificationData {
  id: number;
  source_type: string;
  source_id: number;
  title: string;
  excerpt: string | null;
  read_at: string | null;
  created_at: string | null;
}

export async function getNotifications(): Promise<NotificationData[]> {
  return apiClient("/me/notifications");
}

export async function getUnreadCount(): Promise<{ count: number }> {
  return apiClient("/me/notifications/unread-count");
}

export async function markNotificationsRead(body: {
  ids?: number[];
  all?: boolean;
}): Promise<{ updated: number }> {
  return apiClient("/me/notifications/mark-read", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getMyAnnouncements(): Promise<AnnouncementData[]> {
  return apiClient("/me/announcements");
}
