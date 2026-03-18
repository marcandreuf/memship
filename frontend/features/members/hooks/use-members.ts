"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  changeMemberStatus,
  createMember,
  deleteMember,
  getMember,
  listMembers,
  listMembershipTypes,
  updateMember,
  updateMembershipType,
  deleteMembershipType,
  type ListMembersParams,
} from "../services/members-api";

const MEMBERS_KEY = ["members"];
const MEMBERSHIP_TYPES_KEY = ["membership-types"];

export function useMembers(params: ListMembersParams = {}) {
  return useQuery({
    queryKey: [...MEMBERS_KEY, params],
    queryFn: () => listMembers(params),
  });
}

export function useMember(id: number) {
  return useQuery({
    queryKey: [...MEMBERS_KEY, id],
    queryFn: () => getMember(id),
    enabled: id > 0,
  });
}

export function useMembershipTypes() {
  return useQuery({
    queryKey: MEMBERSHIP_TYPES_KEY,
    queryFn: listMembershipTypes,
  });
}

export function useUpdateMembershipType() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
      updateMembershipType(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MEMBERSHIP_TYPES_KEY });
    },
  });
}

export function useDeleteMembershipType() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteMembershipType,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MEMBERSHIP_TYPES_KEY });
    },
  });
}

export function useCreateMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createMember,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MEMBERS_KEY });
    },
  });
}

export function useUpdateMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
      updateMember(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MEMBERS_KEY });
    },
  });
}

export function useDeleteMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteMember,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MEMBERS_KEY });
    },
  });
}

export function useChangeMemberStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      status,
      reason,
    }: {
      id: number;
      status: string;
      reason?: string;
    }) => changeMemberStatus(id, status, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MEMBERS_KEY });
    },
  });
}
