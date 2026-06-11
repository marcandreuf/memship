"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getBillingRuns,
  getBillingRun,
  runBillingNow,
  type BillingFrequency,
  type BillingRunFilters,
} from "../services/billing-runs-api";

export function useBillingRuns(filters: BillingRunFilters = {}) {
  return useQuery({
    queryKey: ["billing-runs", filters],
    queryFn: () => getBillingRuns(filters),
  });
}

export function useBillingRun(id: number) {
  return useQuery({
    queryKey: ["billing-runs", id],
    queryFn: () => getBillingRun(id),
    enabled: Number.isFinite(id) && id > 0,
  });
}

export function useRunBillingNow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (frequency?: BillingFrequency) => runBillingNow(frequency),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["billing-runs"] });
      queryClient.invalidateQueries({ queryKey: ["receipts"] });
    },
  });
}
