"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listActivities, getActivity, createActivity, updateActivity, deleteActivity,
  publishActivity, archiveActivity, cancelActivity,
  createModality, updateModality, deleteModality,
  createPrice, updatePrice, deletePrice,
  type ListActivitiesParams,
} from "../services/activities-api";

export function useActivities(params: ListActivitiesParams = {}) {
  return useQuery({
    queryKey: ["activities", params],
    queryFn: () => listActivities(params),
  });
}

export function useActivity(id: number) {
  return useQuery({
    queryKey: ["activities", id],
    queryFn: () => getActivity(id),
    enabled: id > 0,
  });
}

export function useCreateActivity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createActivity,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["activities"] }),
  });
}

export function useUpdateActivity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) => updateActivity(id, data),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["activities"] });
      qc.invalidateQueries({ queryKey: ["activities", vars.id] });
    },
  });
}

export function useDeleteActivity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteActivity,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["activities"] }),
  });
}

export function usePublishActivity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: publishActivity,
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["activities"] });
      qc.invalidateQueries({ queryKey: ["activities", id] });
    },
  });
}

export function useArchiveActivity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: archiveActivity,
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["activities"] });
      qc.invalidateQueries({ queryKey: ["activities", id] });
    },
  });
}

export function useCancelActivity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: cancelActivity,
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["activities"] });
      qc.invalidateQueries({ queryKey: ["activities", id] });
    },
  });
}

// Modalities
export function useCreateModality(activityId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => createModality(activityId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["activities", activityId] }),
  });
}

export function useUpdateModality(activityId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ modalityId, data }: { modalityId: number; data: Record<string, unknown> }) => updateModality(activityId, modalityId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["activities", activityId] }),
  });
}

export function useDeleteModality(activityId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (modalityId: number) => deleteModality(activityId, modalityId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["activities", activityId] }),
  });
}

// Prices
export function useCreatePrice(activityId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => createPrice(activityId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["activities", activityId] }),
  });
}

export function useUpdatePrice(activityId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ priceId, data }: { priceId: number; data: Record<string, unknown> }) => updatePrice(activityId, priceId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["activities", activityId] }),
  });
}

export function useDeletePrice(activityId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (priceId: number) => deletePrice(activityId, priceId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["activities", activityId] }),
  });
}
