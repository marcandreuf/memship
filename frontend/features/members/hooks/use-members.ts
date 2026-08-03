"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  approveMember,
  changeMemberStatus,
  createMember,
  getMember,
  listMembers,
  listMemberRegistrations,
  listMembershipTypes,
  rejectMember,
  updateMember,
  updateMembershipType,
  deleteMembershipType,
  type ListMembersParams,
} from "../services/members-api";

const MEMBERS_KEY = ["members"];
const MEMBERSHIP_TYPES_KEY = ["membership-types"];

/** `enabled` exists for callers that render for both staff and members: the
 *  list is `members.read`-guarded, so asking without the key is a guaranteed
 *  403 and an error toast. */
export function useMembers(params: ListMembersParams = {}, enabled = true) {
  return useQuery({
    queryKey: [...MEMBERS_KEY, params],
    queryFn: () => listMembers(params),
    enabled,
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

export function useMemberRegistrations(memberId: number, params: { page?: number; status?: string } = {}) {
  return useQuery({
    queryKey: ["member-registrations", memberId, params],
    queryFn: () => listMemberRegistrations(memberId, params),
    enabled: memberId > 0,
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

export function useApproveMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => approveMember(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MEMBERS_KEY });
    },
  });
}

export function useRejectMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: number; reason?: string }) =>
      rejectMember(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MEMBERS_KEY });
    },
  });
}
