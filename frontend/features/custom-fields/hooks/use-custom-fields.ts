"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createCustomField,
  deleteCustomField,
  getMyCustomFields,
  getPersonCustomFields,
  listCustomFields,
  updateCustomField,
  updateMyCustomFields,
  updatePersonCustomFields,
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

export function usePersonCustomFields(personId: number) {
  return useQuery({
    queryKey: ["custom-field-values", personId],
    queryFn: () => getPersonCustomFields(personId),
    enabled: personId > 0,
  });
}

export function useUpdatePersonCustomFields(personId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: Record<string, string | boolean | null>) =>
      updatePersonCustomFields(personId, values),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["custom-field-values", personId],
      }),
  });
}

export function useMyCustomFields(enabled = true) {
  return useQuery({
    queryKey: ["custom-field-values", "me"],
    queryFn: getMyCustomFields,
    enabled,
  });
}

export function useUpdateMyCustomFields() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateMyCustomFields,
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["custom-field-values", "me"],
      }),
  });
}
