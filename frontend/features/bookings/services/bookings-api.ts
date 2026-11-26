import { apiClient } from "@/lib/client-api";
import type { PaymentMethod } from "@/features/activities/services/activities-api";

// `legacy` books at once and bills afterwards; `pay_to_confirm` holds a paid
// booking until its receipt is paid (#603). A space may move from legacy to
// pay_to_confirm, never back.
export type SpacePaymentFlow = "legacy" | "pay_to_confirm";

export interface Space {
  id: number;
  name: string;
  space_type: string | null;
  description: string | null;
  // What one booking costs, before tax. null or 0 = free, and nothing is billed.
  price: number | null;
  open_time: string; // "HH:MM:SS"
  close_time: string;
  // Membership type ids allowed to book. null or empty = open to every member.
  allowed_membership_types: number[] | null;
  is_active: boolean;
  payment_flow: SpacePaymentFlow;
  payment_methods: PaymentMethod[];
  // Override of the club's booking auto-cancel default; null inherits it.
  auto_cancel_enabled: boolean | null;
  auto_cancel_hours: number | null;
  // Refund deadline before a slot starts; null inherits the club's default (#604).
  cancellation_deadline_minutes: number | null;
  late_cancellation_mode: "block" | "allow_no_refund";
  created_at: string | null;
  updated_at: string | null;
}

export interface SpaceInput {
  name: string;
  space_type: string | null;
  description: string | null;
  price: number | null;
  open_time: string;
  close_time: string;
  allowed_membership_types: number[];
  is_active?: boolean;
  payment_flow?: "pay_to_confirm";
  payment_methods?: PaymentMethod[];
  auto_cancel_enabled?: boolean | null;
  auto_cancel_hours?: number | null;
  cancellation_deadline_minutes?: number | null;
  late_cancellation_mode?: "block" | "allow_no_refund";
}

export interface SpacePaymentOptions {
  usable_methods: PaymentMethod[];
  auto_cancel_enabled: boolean;
  auto_cancel_hours: number;
  switched_off_templates: string[];
}

export interface SpaceSlot {
  id: number;
  space_id: number;
  slot_date: string; // "YYYY-MM-DD"
  start_time: string;
  end_time: string;
  capacity: number;
  // Overrides the space's price for this slot; null falls back to the space.
  price: number | null;
  series_id: string | null;
  is_active: boolean;
  // Slots of this slot's series dated on/after it (itself included).
  series_size_upcoming: number;
}

export interface SlotRepeat {
  weekdays: number[]; // 0=Mon … 6=Sun
  interval_weeks: number;
  count: number;
}

export interface SpaceSlotInput {
  slot_date: string;
  start_time?: string;
  end_time?: string;
  all_day?: boolean;
  capacity: number;
  price?: number | null;
  is_active?: boolean;
  repeat?: SlotRepeat;
}

export type SlotApplyTo = "one" | "upcoming";

export type BookingStatus = "booked" | "pending" | "waitlisted" | "cancelled";

export interface AdminBooking {
  id: number;
  space_slot_id: number;
  party_id: number;
  member_name: string;
  slot_date: string; // "YYYY-MM-DD"
  start_time: string;
  end_time: string;
  status: BookingStatus;
  // While pending: when it must be paid by. Its latest receipt, if any.
  payment_due_at: string | null;
  receipt_id: number | null;
  receipt_status: string | null;
  receipt_due_date: string | null;
  refund_status: "none" | "due" | "returned";
  late_payment_at: string | null;
  cancelled_cause: string | null;
}

export interface PageMeta {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

export interface AdminBookingPage {
  meta: PageMeta;
  items: AdminBooking[];
}

// Dashboard aggregate over active slots in the next `window_days` days.
// `active_spaces` is not windowed.
export interface SpaceStats {
  window_days: number;
  booked: number;
  pending: number;
  waitlisted: number;
  cancelled: number;
  total: number;
  active_spaces: number;
  slots: number;
  capacity: number;
  occupancy_pct: number;
}

// --- Spaces (admin) ---

export async function getSpaceStats(): Promise<SpaceStats> {
  return apiClient<SpaceStats>("/spaces/stats");
}

export async function listSpaces(): Promise<Space[]> {
  return apiClient<Space[]>("/spaces");
}

export async function getSpace(id: number): Promise<Space> {
  return apiClient<Space>(`/spaces/${id}`);
}

export async function createSpace(data: SpaceInput): Promise<Space> {
  return apiClient<Space>("/spaces", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// Narrowing the hours past existing upcoming slots answers 409 +
// {slots_outside_hours, affected_members} without force — the UI confirms,
// then retries with force and those slots are deleted.
export async function updateSpace(
  id: number,
  data: Partial<SpaceInput>,
  force = false
): Promise<Space> {
  return apiClient<Space>(`/spaces/${id}${force ? "?force=true" : ""}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

// Destructive delete; deactivation (the default path) is updateSpace({is_active:false}).
// Without force the backend answers 409 + {affected_members} when active future
// bookings exist — the UI confirms, then retries with force.
export async function deleteSpace(id: number, force = false): Promise<void> {
  return apiClient<void>(`/spaces/${id}${force ? "?force=true" : ""}`, {
    method: "DELETE",
  });
}

// --- Slots (admin) ---

export async function listSlots(spaceId: number): Promise<SpaceSlot[]> {
  return apiClient<SpaceSlot[]>(`/spaces/${spaceId}/slots`);
}

export async function createSlot(
  spaceId: number,
  data: SpaceSlotInput
): Promise<SpaceSlot[]> {
  return apiClient<SpaceSlot[]>(`/spaces/${spaceId}/slots`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateSlot(
  spaceId: number,
  slotId: number,
  data: Partial<SpaceSlotInput>,
  applyTo: SlotApplyTo = "one"
): Promise<SpaceSlot> {
  return apiClient<SpaceSlot>(
    `/spaces/${spaceId}/slots/${slotId}?apply_to=${applyTo}`,
    {
      method: "PUT",
      body: JSON.stringify(data),
    }
  );
}

export async function deleteSlot(
  spaceId: number,
  slotId: number,
  force = false
): Promise<void> {
  return apiClient<void>(
    `/spaces/${spaceId}/slots/${slotId}${force ? "?force=true" : ""}`,
    { method: "DELETE" }
  );
}

// --- Bookings ---

export async function listSpaceBookings(
  spaceId: number,
  params: { page?: number; per_page?: number; status?: string } = {}
): Promise<AdminBookingPage> {
  const q = new URLSearchParams();
  if (params.page) q.set("page", String(params.page));
  if (params.per_page) q.set("per_page", String(params.per_page));
  if (params.status) q.set("status", params.status);
  const query = q.toString();
  return apiClient<AdminBookingPage>(
    `/spaces/${spaceId}/bookings${query ? `?${query}` : ""}`
  );
}

// `keepPayment` is the club's choice, cancelling a paid booking, not to return
// the money; ignored for a member cancelling their own.
export async function cancelBooking(id: number, keepPayment = false): Promise<void> {
  return apiClient<void>(`/bookings/${id}${keepPayment ? "?keep_payment=true" : ""}`, {
    method: "DELETE",
  });
}

export async function confirmBookingWithoutPayment(id: number): Promise<void> {
  return apiClient<void>(`/bookings/${id}/confirm-without-payment`, { method: "POST" });
}

export async function getSpacePaymentOptions(): Promise<SpacePaymentOptions> {
  return apiClient<SpacePaymentOptions>("/spaces/payment-options");
}

// --- Member: availability + booking ---

// `too_late`: too close to the start to be held until paid, so not bookable.
export type CellState = "open" | "full" | "past" | "out_of_window" | "too_late";
export type MyStatus = "none" | "booked" | "pending" | "waitlisted";

export interface AvailabilityCell {
  space_slot_id: number;
  date: string; // "YYYY-MM-DD"
  weekday: number;
  start_time: string;
  end_time: string;
  capacity: number;
  // The slot's own price, or the space's, or 0 — before tax.
  price: number;
  // In a pay-to-confirm space: when a booking made now must be paid by.
  pay_by: string | null;
  booked_count: number;
  waitlist_count: number;
  my_status: MyStatus;
  cell_state: CellState;
}

// Why the member may not book this space at all. The two are separate because
// they need separate answers: one is an upgrade, the other is a missing tier
// only the club can assign.
export type IneligibleReason =
  | "membership_type_not_allowed"
  | "no_membership_type";

export interface WeekAvailability {
  space_id: number;
  week_start: string;
  eligible: boolean;
  ineligible_reason: IneligibleReason | null;
  cells: AvailabilityCell[];
}

export interface MyBooking {
  id: number;
  space_slot_id: number;
  space_id: number;
  space_name: string;
  slot_date: string;
  start_time: string;
  end_time: string;
  status: BookingStatus;
  capacity: number;
  booked_count: number;
  waitlist_position: number | null;
  /** False once the self-cancellation deadline has passed. */
  can_cancel: boolean;
  /** False when cancelling is allowed but the club keeps what was paid. */
  cancel_refundable: boolean;
  // A booking held until paid: by when, and the receipt to pay.
  payment_due_at: string | null;
  receipt_id: number | null;
}

export interface BookingResult {
  id: number;
  space_slot_id: number;
  party_id: number;
  status: BookingStatus;
}

export async function listAvailableSpaces(): Promise<Space[]> {
  return apiClient<Space[]>("/spaces-available");
}

export async function getAvailability(
  spaceId: number,
  weekStart: string
): Promise<WeekAvailability> {
  return apiClient<WeekAvailability>(
    `/spaces/${spaceId}/availability?week_start=${weekStart}`
  );
}

export async function createBooking(
  spaceSlotId: number
): Promise<BookingResult> {
  return apiClient<BookingResult>("/bookings", {
    method: "POST",
    body: JSON.stringify({ space_slot_id: spaceSlotId }),
  });
}

export async function getMyBookings(
  scope: "upcoming" | "past"
): Promise<MyBooking[]> {
  return apiClient<MyBooking[]>(`/me/bookings?scope=${scope}`);
}
