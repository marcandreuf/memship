import { apiClient } from "@/lib/client-api";

/**
 * A seat is a registration or a space booking. Both can be owed back and
 * both can be paid too late, so the club sees them in one list each (#603).
 */
export type SeatKind = "registration" | "booking";

export type RefundStatus = "none" | "due" | "returned";

export interface SeatPageMeta {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

export interface RefundData {
  kind: SeatKind;
  seat_id: number;
  /** The activity, or the space. */
  owner_id: number;
  /** The activity's name, or the space with the slot's date and time. */
  owner_name: string;
  member_name: string | null;
  member_number: string | null;
  cancelled_at: string | null;
  refund_status: RefundStatus;
  receipt_id: number;
  receipt_number: string;
  amount: number;
  payment_method: string | null;
  payment_date: string | null;
  /** What finds the payment in the gateway's dashboard. */
  gateway_reference: string | null;
  refund_returned_at: string | null;
  refund_credit_note_id: number | null;
}

export interface LatePaymentData {
  kind: SeatKind;
  seat_id: number;
  owner_id: number;
  owner_name: string;
  member_name: string | null;
  status: string;
  refund_status: RefundStatus;
  late_payment_at: string;
}

/** Where the club sees the seat: its activity, or its space. */
export function seatOwnerHref(seat: { kind: SeatKind; owner_id: number }): string {
  return seat.kind === "booking"
    ? `/spaces/${seat.owner_id}`
    : `/activities/${seat.owner_id}`;
}

export async function listRefunds(params: {
  page?: number;
  per_page?: number;
  refund_status?: "due" | "returned";
}): Promise<{ items: RefundData[]; meta: SeatPageMeta }> {
  const sp = new URLSearchParams();
  if (params.page) sp.set("page", String(params.page));
  if (params.per_page) sp.set("per_page", String(params.per_page));
  if (params.refund_status) sp.set("refund_status", params.refund_status);
  const qs = sp.toString();
  return apiClient(`/seats/refunds${qs ? `?${qs}` : ""}`);
}

export async function markRefundReturned(kind: SeatKind, seatId: number): Promise<RefundData> {
  return apiClient(`/seats/${kind}/${seatId}/refund-returned`, { method: "POST" });
}

export async function listUnseenLatePayments(): Promise<{ items: LatePaymentData[] }> {
  return apiClient("/seats/late-payments");
}

export async function acknowledgeLatePayment(kind: SeatKind, seatId: number): Promise<void> {
  await apiClient(`/seats/${kind}/${seatId}/late-payment-seen`, { method: "POST" });
}
