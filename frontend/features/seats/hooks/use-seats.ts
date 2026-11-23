"use client";

import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import {
  acknowledgeLatePayment,
  listRefunds,
  listUnseenLatePayments,
  markRefundReturned,
  type SeatKind,
} from "../services/seats-api";

type SeatRef = { kind: SeatKind; seatId: number };

function invalidateSeats(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: ["refunds"] });
  qc.invalidateQueries({ queryKey: ["late-payments"] });
  qc.invalidateQueries({ queryKey: ["activity-registrations"] });
  qc.invalidateQueries({ queryKey: ["space-bookings"] });
}

export function useRefunds(params: { page?: number; refund_status?: "due" | "returned" }) {
  return useQuery({
    queryKey: ["refunds", params],
    queryFn: () => listRefunds({ ...params, per_page: 20 }),
  });
}

export function useMarkRefundReturned() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ kind, seatId }: SeatRef) => markRefundReturned(kind, seatId),
    onSuccess: () => invalidateSeats(qc),
  });
}

export function useUnseenLatePayments(enabled = true) {
  return useQuery({
    queryKey: ["late-payments"],
    queryFn: listUnseenLatePayments,
    enabled,
  });
}

export function useAcknowledgeLatePayment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ kind, seatId }: SeatRef) => acknowledgeLatePayment(kind, seatId),
    onSuccess: () => invalidateSeats(qc),
  });
}
