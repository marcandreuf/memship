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
    // `showSaveError` on the settings screen names the fields an incomplete
    // provider is missing, which is more than the generic handler can say. A
    // hook-level onError replaces the global toast, the same way `useScanCard`
    // opts out, so the specific message no longer arrives beside a vaguer one
    // (#378).
    onError: () => {},
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["payment-providers"] }),
  });
}

export function useUpdatePaymentProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
      updatePaymentProvider(id, data),
    // `showSaveError` on the settings screen names the fields an incomplete
    // provider is missing, which is more than the generic handler can say. A
    // hook-level onError replaces the global toast, the same way `useScanCard`
    // opts out, so the specific message no longer arrives beside a vaguer one
    // (#378).
    onError: () => {},
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
    // `showSaveError` on the settings screen names the fields an incomplete
    // provider is missing, which is more than the generic handler can say. A
    // hook-level onError replaces the global toast, the same way `useScanCard`
    // opts out, so the specific message no longer arrives beside a vaguer one
    // (#378).
    onError: () => {},
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["payment-providers"] }),
  });
}

export function useTestPaymentProvider() {
  return useMutation({
    mutationFn: testPaymentProvider,
  });
}
