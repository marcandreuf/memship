"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listGroups, getGroup, createGroup, updateGroup, deleteGroup } from "../services/groups-api";

export function useGroups() {
  return useQuery({
    queryKey: ["groups"],
    queryFn: listGroups,
  });
}

export function useGroup(id: number) {
  return useQuery({
    queryKey: ["groups", id],
    queryFn: () => getGroup(id),
    enabled: id > 0,
  });
}

export function useCreateGroup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createGroup,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["groups"] }),
  });
}

export function useUpdateGroup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
      updateGroup(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["groups"] }),
  });
}

export function useDeleteGroup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteGroup,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["groups"] }),
  });
}
