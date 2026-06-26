"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getMyAnnouncements,
  getNotifications,
  getUnreadCount,
  markNotificationsRead,
} from "../services/notifications-api";

export function useUnreadCount(enabled = true) {
  return useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: getUnreadCount,
    enabled,
    refetchInterval: 60_000, // poll the badge
  });
}

export function useNotifications(enabled = true) {
  return useQuery({
    queryKey: ["notifications", "list"],
    queryFn: getNotifications,
    enabled,
  });
}

export function useMarkRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { ids?: number[]; all?: boolean }) =>
      markNotificationsRead(body),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });
}

export function useMyAnnouncements(enabled = true) {
  return useQuery({
    queryKey: ["my-announcements"],
    queryFn: getMyAnnouncements,
    enabled,
  });
}
