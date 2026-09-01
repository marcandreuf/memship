"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getCommunicationsConfig,
  updateCommunicationsConfig,
} from "../services/communications-api";

export function useCommunicationsConfig() {
  return useQuery({
    queryKey: ["communications-config"],
    queryFn: getCommunicationsConfig,
  });
}

export function useUpdateCommunicationsConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateCommunicationsConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["communications-config"] });
    },
  });
}
