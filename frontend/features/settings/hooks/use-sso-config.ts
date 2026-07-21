"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getSsoConfig, updateSsoConfig } from "../services/sso-api";

export function useSsoConfig() {
  return useQuery({
    queryKey: ["sso-config"],
    queryFn: getSsoConfig,
  });
}

export function useUpdateSsoConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateSsoConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sso-config"] });
      // The login/register pages read which providers are live from this.
      queryClient.invalidateQueries({ queryKey: ["sso-providers"] });
    },
  });
}