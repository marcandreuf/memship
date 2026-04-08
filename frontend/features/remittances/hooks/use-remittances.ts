"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getRemittances,
  getRemittance,
  createRemittance,
  generateRemittanceXml,
  markRemittanceSubmitted,
  importRemittanceReturns,
  closeRemittance,
  cancelRemittance,
} from "../services/remittances-api";

export function useRemittances(params?: URLSearchParams) {
  return useQuery({
    queryKey: ["remittances", params?.toString()],
    queryFn: () => getRemittances(params),
  });
}

export function useRemittance(id: number) {
  return useQuery({
    queryKey: ["remittances", id],
    queryFn: () => getRemittance(id),
    enabled: id > 0,
  });
}

export function useCreateRemittance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createRemittance,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["remittances"] });
      qc.invalidateQueries({ queryKey: ["receipts"] });
    },
  });
}

export function useGenerateRemittanceXml() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: generateRemittanceXml,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["remittances"] }),
  });
}

export function useMarkRemittanceSubmitted() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: markRemittanceSubmitted,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["remittances"] }),
  });
}

export function useImportRemittanceReturns() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Array<{ receipt_number: string; reason: string }> }) =>
      importRemittanceReturns(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["remittances"] });
      qc.invalidateQueries({ queryKey: ["receipts"] });
    },
  });
}

export function useCloseRemittance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: closeRemittance,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["remittances"] }),
  });
}

export function useCancelRemittance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: cancelRemittance,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["remittances"] });
      qc.invalidateQueries({ queryKey: ["receipts"] });
    },
  });
}
