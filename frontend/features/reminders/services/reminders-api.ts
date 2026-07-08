import { apiClient } from "@/lib/client-api";

export interface Reminder {
  id: number;
  content: string;
  due_date: string | null;
  is_done: boolean;
  created_by: number | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ReminderCreateInput {
  content: string;
  due_date?: string | null;
}

export interface ReminderUpdateInput {
  content?: string;
  // Pass null to clear the date (turn a reminder back into a note); omit to leave it.
  due_date?: string | null;
  is_done?: boolean;
}

export function getReminders(onlyOpen = false): Promise<Reminder[]> {
  const qs = onlyOpen ? "?only_open=true" : "";
  return apiClient<Reminder[]>(`/reminders${qs}`);
}

export function createReminder(data: ReminderCreateInput): Promise<Reminder> {
  return apiClient<Reminder>("/reminders", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateReminder(
  id: number,
  data: ReminderUpdateInput
): Promise<Reminder> {
  return apiClient<Reminder>(`/reminders/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteReminder(id: number): Promise<void> {
  return apiClient<void>(`/reminders/${id}`, { method: "DELETE" });
}
