"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  cancelBooking,
  createSlot,
  createSpace,
  deactivateSpace,
  deleteSlot,
  getSpace,
  listSlots,
  listSpaceBookings,
  listSpaces,
  updateSlot,
  updateSpace,
  type SpaceInput,
  type SpaceSlotInput,
} from "../services/bookings-api";

export function useSpaces(enabled = true) {
  return useQuery({
    queryKey: ["spaces"],
    queryFn: listSpaces,
    enabled,
  });
}

export function useSpace(id: number) {
  return useQuery({
    queryKey: ["space", id],
    queryFn: () => getSpace(id),
    enabled: id > 0,
  });
}

export function useCreateSpace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createSpace,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["spaces"] }),
  });
}

export function useUpdateSpace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<SpaceInput> }) =>
      updateSpace(id, data),
    onSuccess: (_res, { id }) => {
      qc.invalidateQueries({ queryKey: ["spaces"] });
      qc.invalidateQueries({ queryKey: ["space", id] });
    },
  });
}

export function useDeactivateSpace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deactivateSpace,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["spaces"] }),
  });
}

export function useSlots(spaceId: number, enabled = true) {
  return useQuery({
    queryKey: ["space-slots", spaceId],
    queryFn: () => listSlots(spaceId),
    enabled: enabled && spaceId > 0,
  });
}

export function useCreateSlot(spaceId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: SpaceSlotInput) => createSlot(spaceId, data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["space-slots", spaceId] }),
  });
}

export function useUpdateSlot(spaceId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ slotId, data }: { slotId: number; data: Partial<SpaceSlotInput> }) =>
      updateSlot(spaceId, slotId, data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["space-slots", spaceId] }),
  });
}

export function useDeleteSlot(spaceId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (slotId: number) => deleteSlot(spaceId, slotId),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["space-slots", spaceId] }),
  });
}

export function useSpaceBookings(
  spaceId: number,
  params: { page?: number; per_page?: number; status?: string } = {},
  enabled = true
) {
  return useQuery({
    queryKey: ["space-bookings", spaceId, params],
    queryFn: () => listSpaceBookings(spaceId, params),
    enabled: enabled && spaceId > 0,
  });
}

export function useCancelBooking(spaceId?: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: cancelBooking,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["space-bookings", spaceId] });
      qc.invalidateQueries({ queryKey: ["my-bookings"] });
    },
  });
}
