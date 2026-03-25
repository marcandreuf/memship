"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getSettings, updateSettings, getAddress, updateAddress } from "../services/settings-api";

export function useSettings() {
  return useQuery({
    queryKey: ["settings"],
    queryFn: getSettings,
  });
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateSettings,
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
