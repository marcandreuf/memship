"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getContacts, createContact, updateContact, deleteContact } from "../services/contacts-api";

export function useContacts(personId: number) {
  return useQuery({
    queryKey: ["contacts", personId],
    queryFn: () => getContacts(personId),
    enabled: personId > 0,
  });
}

export function useCreateContact(personId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => createContact(personId, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["contacts", personId] }),
  });
}

export function useUpdateContact(personId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ contactId, data }: { contactId: number; data: Record<string, unknown> }) =>
      updateContact(contactId, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["contacts", personId] }),
  });
}

export function useDeleteContact(personId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (contactId: number) => deleteContact(contactId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["contacts", personId] }),
  });
}
