"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listActivities, getActivity, createActivity, updateActivity, deleteActivity,
  publishActivity, archiveActivity, cancelActivity,
  createModality, updateModality, deleteModality,
  createPrice, updatePrice, deletePrice,
  listDiscountCodes, createDiscountCode, updateDiscountCode, deleteDiscountCode,
  listConsents, createConsent, updateConsent, deleteConsent,
  listAttachmentTypes, createAttachmentType, updateAttachmentType, deleteAttachmentType,
  uploadCoverImage, deleteCoverImage,
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

// Discount Codes
export function useDiscountCodes(activityId: number) {
  return useQuery({
    queryKey: ["discount-codes", activityId],
    queryFn: () => listDiscountCodes(activityId),
    enabled: activityId > 0,
  });
}

export function useCreateDiscountCode(activityId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => createDiscountCode(activityId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["discount-codes", activityId] }),
  });
}

export function useUpdateDiscountCode(activityId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ codeId, data }: { codeId: number; data: Record<string, unknown> }) => updateDiscountCode(activityId, codeId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["discount-codes", activityId] }),
  });
}

export function useDeleteDiscountCode(activityId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (codeId: number) => deleteDiscountCode(activityId, codeId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["discount-codes", activityId] }),
  });
}

// Consents
export function useConsents(activityId: number) {
  return useQuery({
    queryKey: ["activity-consents", activityId],
    queryFn: () => listConsents(activityId),
    enabled: activityId > 0,
  });
}

export function useCreateConsent(activityId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => createConsent(activityId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["activity-consents", activityId] }),
  });
}

export function useUpdateConsent(activityId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ consentId, data }: { consentId: number; data: Record<string, unknown> }) => updateConsent(activityId, consentId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["activity-consents", activityId] }),
  });
}

export function useDeleteConsent(activityId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (consentId: number) => deleteConsent(activityId, consentId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["activity-consents", activityId] }),
  });
}

// Attachment Types
export function useAttachmentTypes(activityId: number) {
  return useQuery({
    queryKey: ["attachment-types", activityId],
    queryFn: () => listAttachmentTypes(activityId),
    enabled: activityId > 0,
  });
}

export function useCreateAttachmentType(activityId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => createAttachmentType(activityId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["attachment-types", activityId] }),
  });
}

export function useUpdateAttachmentType(activityId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ typeId, data }: { typeId: number; data: Record<string, unknown> }) => updateAttachmentType(activityId, typeId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["attachment-types", activityId] }),
  });
}

export function useDeleteAttachmentType(activityId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (typeId: number) => deleteAttachmentType(activityId, typeId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["attachment-types", activityId] }),
  });
}

// Cover Image
export function useUploadCoverImage(activityId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => uploadCoverImage(activityId, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["activities", activityId] });
      qc.invalidateQueries({ queryKey: ["activities"] });
    },
  });
}

export function useDeleteCoverImage(activityId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => deleteCoverImage(activityId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["activities", activityId] });
      qc.invalidateQueries({ queryKey: ["activities"] });
    },
  });
}
