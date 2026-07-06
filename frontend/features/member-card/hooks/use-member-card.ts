"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getMyCard, assignMemberNumbers } from "../services/member-card-api";

export function useMyCard() {
  return useQuery({
    queryKey: ["me", "card"],
    queryFn: getMyCard,
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
