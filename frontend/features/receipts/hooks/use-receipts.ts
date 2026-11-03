"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getReceipts,
  getReceipt,
  getReceiptStats,
  getMyReceipts,
  createReceipt,
  updateReceipt,
  emitReceipt,
  payReceipt,
  cancelReceipt,
  returnReceipt,
  reemitReceipt,
  createCreditNote,
  generateMembershipFees,
  getConcepts,
  createConcept,
  createStripeCheckout,
  getReceiptByStripeSession,
  initiateRedsysPayment,
  getRedsysReturnStatus,
} from "../services/receipts-api";
import type { CreditNotePayload, PayReceiptData, RedsysMethod, RedsysLocale } from "../services/receipts-api";

export function useReceipts(params?: URLSearchParams, enabled = true) {
  return useQuery({
    queryKey: ["receipts", params?.toString()],
    queryFn: () => getReceipts(params),
    enabled,
  });
}

export function useReceiptStats(enabled = true) {
  return useQuery({
    queryKey: ["receipt-stats"],
    queryFn: getReceiptStats,
    enabled,
  });
}

export function useMyReceipts(params?: URLSearchParams, enabled = true) {
  return useQuery({
    queryKey: ["my-receipts", params?.toString()],
    queryFn: () => getMyReceipts(params),
    enabled,
  });
}

export function useReceipt(id: number) {
  return useQuery({
    queryKey: ["receipts", id],
    queryFn: () => getReceipt(id),
    enabled: id > 0,
  });
}

export function useCreateReceipt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createReceipt,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["receipts"] }),
  });
}

export function useUpdateReceipt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
      updateReceipt(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["receipts"] }),
  });
}

export function useEmitReceipt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: emitReceipt,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["receipts"] }),
  });
}

export function usePayReceipt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: PayReceiptData }) =>
      payReceipt(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["receipts"] }),
  });
}

export function useCancelReceipt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: cancelReceipt,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["receipts"] }),
  });
}

export function useReturnReceipt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: { return_reason: string; return_date?: string } }) =>
      returnReceipt(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["receipts"] }),
  });
}

export function useReemitReceipt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: reemitReceipt,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["receipts"] }),
  });
}

export function useCreateCreditNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: CreditNotePayload }) =>
      createCreditNote(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["receipts"] });
      qc.invalidateQueries({ queryKey: ["receipt-stats"] });
    },
  });
}

export function useGenerateMembershipFees() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: generateMembershipFees,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["receipts"] }),
  });
}

export function useConcepts(type?: string) {
  return useQuery({
    queryKey: ["concepts", type],
    queryFn: () => getConcepts(type),
    staleTime: 5 * 60 * 1000,
  });
}

export function useCreateConcept() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createConcept,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["concepts"] }),
  });
}

// --- Stripe Checkout ---

export function useStripeCheckout() {
  return useMutation({
    mutationFn: createStripeCheckout,
  });
}

const POLL_INTERVAL_MS = 2000;
const STRIPE_POLL_ATTEMPTS = 5;
const REDSYS_POLL_ATTEMPTS = 15;
/** How long each return page waits for the gateway's confirmation before saying so. */
export const STRIPE_CONFIRMATION_WAIT_MS = POLL_INTERVAL_MS * STRIPE_POLL_ATTEMPTS;
export const REDSYS_CONFIRMATION_WAIT_MS = POLL_INTERVAL_MS * REDSYS_POLL_ATTEMPTS;

/**
 * True once `ms` have passed while `waiting` holds.
 *
 * The return pages stop polling after a fixed window. If the confirmation has
 * not arrived by then it may never come — a rejected notification, a lost one
 * (#514) — and the page must stop implying it is on its way.
 */
export function useWaitedPast(ms: number, waiting: boolean) {
  const [elapsed, setElapsed] = useState(false);
  useEffect(() => {
    if (!waiting) return;
    const timer = setTimeout(() => setElapsed(true), ms);
    return () => clearTimeout(timer);
  }, [ms, waiting]);
  return waiting && elapsed;
}

export function useReceiptByStripeSession(sessionId: string | null) {
  return useQuery({
    queryKey: ["receipt-by-session", sessionId],
    queryFn: () => getReceiptByStripeSession(sessionId!),
    enabled: !!sessionId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && data.status === "paid") return false;
      if ((query.state.dataUpdateCount ?? 0) >= STRIPE_POLL_ATTEMPTS) return false;
      return POLL_INTERVAL_MS;
    },
  });
}

// --- Redsys ---

export function useRedsysInitiate() {
  return useMutation({
    mutationFn: ({
      receiptId,
      method,
      locale,
    }: {
      receiptId: number;
      method?: RedsysMethod;
      locale?: RedsysLocale;
    }) => initiateRedsysPayment(receiptId, { method, locale }),
  });
}

export function useRedsysReturnStatus(receiptId: number | null) {
  return useQuery({
    queryKey: ["redsys-return", receiptId],
    queryFn: () => getRedsysReturnStatus(receiptId!),
    enabled: !!receiptId,
    refetchInterval: (query) => {
      // Authoritative status arrives via the async notification — poll until
      // receipt is in a terminal state or the user has waited ~30s.
      const data = query.state.data;
      const terminal = new Set(["paid", "cancelled", "returned"]);
      if (data && terminal.has(data.status)) return false;
      if ((query.state.dataUpdateCount ?? 0) >= REDSYS_POLL_ATTEMPTS) return false;
      return POLL_INTERVAL_MS;
    },
  });
}
