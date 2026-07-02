"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createAnnouncement,
  getAnnouncement,
  getAnnouncements,
  getAudiencePreview,
  getRecipients,
  getRecipientStats,
  sendAnnouncement,
  updateAnnouncement,
  type AnnouncementFilters,
  type AnnouncementInput,
} from "../services/announcements-api";

export function useAnnouncements(filters: AnnouncementFilters = {}) {
  return useQuery({
    queryKey: ["announcements", filters],
    queryFn: () => getAnnouncements(filters),
  });
}

export function useAnnouncement(id: number) {
  return useQuery({
    queryKey: ["announcements", id],
    queryFn: () => getAnnouncement(id),
    enabled: Number.isFinite(id) && id > 0,
  });
}

export function useCreateAnnouncement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: AnnouncementInput) => createAnnouncement(data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["announcements"] }),
  });
}

export function useUpdateAnnouncement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<AnnouncementInput> }) =>
      updateAnnouncement(id, data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["announcements"] }),
  });
}

export function useSendAnnouncement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => sendAnnouncement(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["announcements"] }),
  });
}

export function useAudiencePreview(id: number, enabled = true) {
  return useQuery({
    queryKey: ["announcements", id, "audience"],
    queryFn: () => getAudiencePreview(id),
    enabled: enabled && Number.isFinite(id) && id > 0,
  });
}

export function useAnnouncementRecipients(
  id: number,
  page: number,
  perPage = 10,
  enabled = true
) {
  return useQuery({
    queryKey: ["announcements", id, "recipients", page, perPage],
    queryFn: () => getRecipients(id, page, perPage),
    enabled: enabled && Number.isFinite(id) && id > 0,
  });
}

export function useAnnouncementStats(id: number, enabled = true) {
  return useQuery({
    queryKey: ["announcements", id, "stats"],
    queryFn: () => getRecipientStats(id),
    enabled: enabled && Number.isFinite(id) && id > 0,
  });
}
