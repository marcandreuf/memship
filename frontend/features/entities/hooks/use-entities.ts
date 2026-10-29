"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createEntity,
  createEntityContact,
  deleteEntity,
  getEntities,
  getEntity,
  getEntityAddress,
  getEntityContacts,
  getEntityKinds,
  searchParties,
  updateEntity,
  updateEntityAddress,
} from "../services/entities-api";
import {
  deleteContact,
  updateContact,
} from "@/features/members/services/contacts-api";

export function useEntities(params?: URLSearchParams) {
  return useQuery({
    queryKey: ["entities", params?.toString()],
    queryFn: () => getEntities(params),
  });
}

export function useEntity(id: number) {
  return useQuery({
    queryKey: ["entities", id],
    queryFn: () => getEntity(id),
    enabled: id > 0,
  });
}

export function useEntityKinds() {
  return useQuery({
    queryKey: ["entity-kinds"],
    queryFn: getEntityKinds,
    staleTime: Infinity,
  });
}

export function useCreateEntity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createEntity,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["entities"] }),
  });
}

export function useUpdateEntity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
      updateEntity(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["entities"] }),
  });
}

export function useDeleteEntity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteEntity,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["entities"] }),
  });
}

export function useEntityAddress(id: number) {
  return useQuery({
    queryKey: ["entities", id, "address"],
    queryFn: () => getEntityAddress(id),
    enabled: id > 0,
  });
}

export function useUpdateEntityAddress(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => updateEntityAddress(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["entities", id, "address"] }),
  });
}

export function usePartySearch(q: string) {
  return useQuery({
    queryKey: ["party-search", q],
    queryFn: () => searchParties(q),
    enabled: q.trim().length > 0,
  });
}

export function useEntityContacts(partyId: number) {
  return useQuery({
    queryKey: ["entity-contacts", partyId],
    queryFn: () => getEntityContacts(partyId),
    enabled: partyId > 0,
  });
}

export function useCreateEntityContact(partyId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => createEntityContact(partyId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["entity-contacts", partyId] }),
  });
}

export function useUpdateEntityContact(partyId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ contactId, data }: { contactId: number; data: Record<string, unknown> }) =>
      updateContact(contactId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["entity-contacts", partyId] }),
  });
}

export function useDeleteEntityContact(partyId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (contactId: number) => deleteContact(contactId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["entity-contacts", partyId] }),
  });
}
