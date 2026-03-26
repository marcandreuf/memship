"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  registerForActivity,
  checkEligibility,
  cancelRegistration,
  changeRegistrationStatus,
  listActivityRegistrations,
  listMyRegistrations,
  listRegistrationAttachments,
  uploadRegistrationAttachment,
  getRegistrationStats,
  type ListRegistrationsParams,
  type RegisterParams,
} from "../services/registrations-api";

export function useEligibility(activityId: number) {
  return useQuery({
    queryKey: ["eligibility", activityId],
    queryFn: () => checkEligibility(activityId),
    enabled: activityId > 0,
  });
}

export function useRegister() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: RegisterParams) => registerForActivity(params),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["activities", vars.activityId] });
      qc.invalidateQueries({ queryKey: ["eligibility", vars.activityId] });
      qc.invalidateQueries({ queryKey: ["activity-registrations", vars.activityId] });
      qc.invalidateQueries({ queryKey: ["my-registrations"] });
      qc.invalidateQueries({ queryKey: ["my-receipts"] });
      qc.invalidateQueries({ queryKey: ["receipts"] });
    },
  });
}

export function useCancelRegistration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: number; reason?: string }) =>
      cancelRegistration(id, reason),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["activities"] });
      qc.invalidateQueries({ queryKey: ["activity-registrations"] });
      qc.invalidateQueries({ queryKey: ["my-registrations"] });
      qc.invalidateQueries({ queryKey: ["eligibility"] });
      qc.invalidateQueries({ queryKey: ["my-receipts"] });
      qc.invalidateQueries({ queryKey: ["receipts"] });
    },
  });
}

export function useChangeRegistrationStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      status,
      admin_notes,
    }: {
      id: number;
      status: string;
      admin_notes?: string;
    }) => changeRegistrationStatus(id, status, admin_notes),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["activities"] });
      qc.invalidateQueries({ queryKey: ["activity-registrations"] });
      qc.invalidateQueries({ queryKey: ["my-registrations"] });
    },
  });
}

export function useActivityRegistrations(params: ListRegistrationsParams) {
  return useQuery({
    queryKey: ["activity-registrations", params.activityId, params],
    queryFn: () => listActivityRegistrations(params),
    enabled: params.activityId > 0,
  });
}

export function useRegistrationStats() {
  return useQuery({
    queryKey: ["registration-stats"],
    queryFn: () => getRegistrationStats(),
  });
}

export function useMyRegistrations(params: { page?: number; per_page?: number } = {}) {
  return useQuery({
    queryKey: ["my-registrations", params],
    queryFn: () => listMyRegistrations(params),
  });
}

export function useRegistrationAttachments(registrationId: number) {
  return useQuery({
    queryKey: ["registration-attachments", registrationId],
    queryFn: () => listRegistrationAttachments(registrationId),
    enabled: registrationId > 0,
  });
}

export function useUploadAttachment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      registrationId,
      file,
      attachmentTypeId,
    }: {
      registrationId: number;
      file: File;
      attachmentTypeId?: number;
    }) => uploadRegistrationAttachment(registrationId, file, attachmentTypeId),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["registration-attachments", vars.registrationId] });
    },
  });
}
