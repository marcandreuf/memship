import { apiClient } from "@/lib/client-api";

export interface ReceiptReminder {
  id: number;
  receipt_id: number;
  reminder_number: number;
  channel: string;
  status: string;
  to_email: string | null;
  triggered_by: string;
  triggered_by_user_id: number | null;
  error: string | null;
  sent_at: string | null;
  created_at: string | null;
}

export async function getReceiptReminders(
  receiptId: number
): Promise<ReceiptReminder[]> {
  return apiClient(`/receipts/${receiptId}/reminders`);
}

export async function sendReceiptReminder(
  receiptId: number
): Promise<ReceiptReminder> {
  return apiClient(`/receipts/${receiptId}/send-reminder`, { method: "POST" });
}
