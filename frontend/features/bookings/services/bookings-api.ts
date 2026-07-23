import { apiClient } from "@/lib/client-api";

export interface Space {
  id: number;
  name: string;
  space_type: string | null;
  description: string | null;
  open_time: string; // "HH:MM:SS"
  close_time: string;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface SpaceInput {
  name: string;
  space_type: string | null;
  description: string | null;
  open_time: string;
  close_time: string;
  is_active?: boolean;
}

export interface SpaceSlot {
  id: number;
  space_id: number;
  slot_date: string; // "YYYY-MM-DD"
  start_time: string;
  end_time: string;
  capacity: number;
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
  is_active?: boolean;
  repeat?: SlotRepeat;
}

export type SlotApplyTo = "one" | "upcoming";

export type BookingStatus = "booked" | "waitlisted" | "cancelled";

export interface AdminBooking {
  id: number;
  space_slot_id: number;
  member_id: number;
  member_name: string;
  slot_date: string; // "YYYY-MM-DD"
  start_time: string;
  end_time: string;
  status: BookingStatus;
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

// --- Spaces (admin) ---

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

export async function updateSpace(
  id: number,
  data: Partial<SpaceInput>
): Promise<Space> {
  return apiClient<Space>(`/spaces/${id}`, {
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

export async function cancelBooking(id: number): Promise<void> {
  return apiClient<void>(`/bookings/${id}`, { method: "DELETE" });
}

// --- Member: availability + booking ---

export type CellState = "open" | "full" | "past" | "out_of_window";
export type MyStatus = "none" | "booked" | "waitlisted";

export interface AvailabilityCell {
  space_slot_id: number;
  date: string; // "YYYY-MM-DD"
  weekday: number;
  start_time: string;
  end_time: string;
  capacity: number;
  booked_count: number;
  waitlist_count: number;
  my_status: MyStatus;
  cell_state: CellState;
}

export interface WeekAvailability {
  space_id: number;
  week_start: string;
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
}

export interface BookingResult {
  id: number;
  space_slot_id: number;
  member_id: number;
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
