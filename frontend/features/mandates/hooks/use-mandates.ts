"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getMandates,
  getMandate,
  createMandate,
  updateMandate,
  cancelMandate,
  uploadSignedMandate,
} from "../services/mandates-api";

export function useMandates(params?: URLSearchParams) {
  return useQuery({
    queryKey: ["mandates", params?.toString()],
    queryFn: () => getMandates(params),
  });
}

export function useMandate(id: number) {
  return useQuery({
    queryKey: ["mandates", id],
    queryFn: () => getMandate(id),
    enabled: id > 0,
  });
}

export function useCreateMandate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createMandate,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mandates"] }),
  });
}

export function useUpdateMandate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
      updateMandate(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mandates"] }),
  });
}

export function useCancelMandate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: cancelMandate,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mandates"] }),
  });
}

export function useUploadSignedMandate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, file }: { id: number; file: File }) =>
      uploadSignedMandate(id, file),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mandates"] }),
  });
}
