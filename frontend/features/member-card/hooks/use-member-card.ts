"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getMyCard,
  getMemberCard,
  assignMemberNumbers,
  scanCard,
} from "../services/member-card-api";

export function useMyCard() {
  return useQuery({
    queryKey: ["me", "card"],
    queryFn: getMyCard,
    retry: false,
  });
}

export function useMemberCard(memberId: number, enabled = true) {
  return useQuery({
    queryKey: ["members", memberId, "card"],
    queryFn: () => getMemberCard(memberId),
    enabled,
    retry: false,
  });
}

export function useAssignMemberNumbers() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: assignMemberNumbers,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["members"] }),
  });
}

export function useScanCard() {
  return useMutation({
    mutationFn: (token: string) => scanCard(token),
    // The scan panel renders the failure itself, translated. A hook-level
    // onError replaces the global toast, which would repeat it in the API's
    // English ("Invalid card code").
    onError: () => {},
  });
}
