"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getPaymentProviders,
  createPaymentProvider,
  updatePaymentProvider,
  deletePaymentProvider,
  togglePaymentProvider,
  testPaymentProvider,
  getProviderTypes,
  getActivePaymentMethods,
} from "../services/payment-providers-api";

export function usePaymentProviders() {
  return useQuery({
    queryKey: ["payment-providers"],
    queryFn: getPaymentProviders,
  });
}

export function useProviderTypes() {
  return useQuery({
    queryKey: ["payment-providers", "types"],
    queryFn: getProviderTypes,
  });
}

export function useActivePaymentMethods() {
  return useQuery({
    queryKey: ["payment-providers", "active-methods"],
    queryFn: getActivePaymentMethods,
    staleTime: 60_000,
  });
}

export function useCreatePaymentProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createPaymentProvider,
    // `showSaveError` names the fields an incomplete provider is missing,
    // which is more than the generic handler can say — so it reports, and the
    // cache-level handler stays quiet rather than adding a vaguer second
    // toast beside it (#378).
    meta: { ownErrorMessage: true },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["payment-providers"] }),
  });
}

export function useUpdatePaymentProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
      updatePaymentProvider(id, data),
    // `showSaveError` names the fields an incomplete provider is missing,
    // which is more than the generic handler can say — so it reports, and the
    // cache-level handler stays quiet rather than adding a vaguer second
    // toast beside it (#378).
    meta: { ownErrorMessage: true },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["payment-providers"] }),
  });
}

export function useDeletePaymentProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deletePaymentProvider,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["payment-providers"] }),
  });
}

export function useTogglePaymentProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: togglePaymentProvider,
    // `showSaveError` names the fields an incomplete provider is missing,
    // which is more than the generic handler can say — so it reports, and the
    // cache-level handler stays quiet rather than adding a vaguer second
    // toast beside it (#378).
    meta: { ownErrorMessage: true },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["payment-providers"] }),
  });
}

export function useTestPaymentProvider() {
  return useMutation({
    mutationFn: testPaymentProvider,
  });
}
