"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createReminder,
  deleteReminder,
  getReminders,
  updateReminder,
  type ReminderCreateInput,
  type ReminderUpdateInput,
} from "../services/reminders-api";

export function useReminders(onlyOpen = false) {
  return useQuery({
    queryKey: ["reminders", { onlyOpen }],
    queryFn: () => getReminders(onlyOpen),
  });
}

export function useCreateReminder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ReminderCreateInput) => createReminder(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reminders"] }),
  });
}

export function useUpdateReminder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ReminderUpdateInput }) =>
      updateReminder(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reminders"] }),
  });
}

export function useDeleteReminder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteReminder(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reminders"] }),
  });
}
