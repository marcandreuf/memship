"use client";

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
  generateMembershipFees,
  getConcepts,
  createConcept,
} from "../services/receipts-api";

export function useReceipts(params?: URLSearchParams) {
  return useQuery({
    queryKey: ["receipts", params?.toString()],
    queryFn: () => getReceipts(params),
  });
}

export function useReceiptStats() {
  return useQuery({
    queryKey: ["receipt-stats"],
    queryFn: getReceiptStats,
  });
}

export function useMyReceipts(params?: URLSearchParams) {
  return useQuery({
    queryKey: ["my-receipts", params?.toString()],
    queryFn: () => getMyReceipts(params),
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
    mutationFn: ({ id, data }: { id: number; data: { payment_method: string; payment_date?: string } }) =>
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
