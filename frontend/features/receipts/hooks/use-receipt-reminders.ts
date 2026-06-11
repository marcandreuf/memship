"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getReceiptReminders,
  sendReceiptReminder,
} from "../services/reminders-api";

export function useReceiptReminders(receiptId: number) {
  return useQuery({
    queryKey: ["receipt-reminders", receiptId],
    queryFn: () => getReceiptReminders(receiptId),
    enabled: Number.isFinite(receiptId) && receiptId > 0,
  });
}

export function useSendReceiptReminder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (receiptId: number) => sendReceiptReminder(receiptId),
    onSuccess: (_data, receiptId) => {
      qc.invalidateQueries({ queryKey: ["receipt-reminders", receiptId] });
      qc.invalidateQueries({ queryKey: ["receipts"] });
    },
  });
}
