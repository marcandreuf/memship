"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getBranding, getSettings, updateSettings, getAddress, updateAddress } from "../services/settings-api";

/** The shell's settings: name, logo, colour, contact block, feature flags.
 *  Every screen that only needs "is this feature on" or "what colour are we"
 *  uses this — it is reachable by any account, staff or not. */
export function useSettings() {
  return useQuery({
    queryKey: ["settings", "branding"],
    queryFn: getBranding,
  });
}

/** The full record — banking, invoice counters, member numbering, SEPA. Behind
 *  `settings.read`, so only the screens that edit org data may ask for it. */
export function useOrgSettings(enabled = true) {
  return useQuery({
    queryKey: ["settings", "org"],
    queryFn: getSettings,
    enabled,
  });
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateSettings,
    // Both views read the same row: a feature toggle written from the org form
    // has to reach the shell, and vice versa.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings"] }),
  });
}

export function useAddress() {
  return useQuery({
    queryKey: ["settings", "address"],
    queryFn: getAddress,
  });
}

export function useUpdateAddress() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateAddress,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "address"] }),
  });
}
