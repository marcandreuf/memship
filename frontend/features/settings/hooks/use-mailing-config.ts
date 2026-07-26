"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getMailingConfig,
  testMailingProvider,
  updateMailingConfig,
} from "../services/mailing-api";

export function useMailingConfig() {
  return useQuery({
    queryKey: ["mailing-config"],
    queryFn: getMailingConfig,
  });
}

export function useUpdateMailingConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateMailingConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mailing-config"] });
    },
  });
}

export function useTestMailingProvider() {
  return useMutation({
    mutationFn: testMailingProvider,
  });
}