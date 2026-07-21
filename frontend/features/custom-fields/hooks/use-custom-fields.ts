"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createCustomField,
  deleteCustomField,
  listCustomFields,
  updateCustomField,
  type CustomFieldDefinitionInput,
} from "../services/custom-fields-api";

/** Definitions are shared by the settings tab and every member's tab. */
export function useCustomFields(includeInactive = false, enabled = true) {
  return useQuery({
    queryKey: ["custom-fields", includeInactive],
    queryFn: () => listCustomFields(includeInactive),
    enabled,
  });
}

export function useCreateCustomField() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createCustomField,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["custom-fields"] }),
  });
}

export function useUpdateCustomField() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number;
      data: Partial<CustomFieldDefinitionInput>;
    }) => updateCustomField(id, data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["custom-fields"] }),
  });
}

export function useDeleteCustomField() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteCustomField,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["custom-fields"] }),
  });
}
