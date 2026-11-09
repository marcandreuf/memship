"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createDonation, getDonationOptions } from "../services/donations-api";

/**
 * The ask and the bounds.
 *
 * Not cached: the message and both bounds are settings an administrator can
 * change while this page is open, and the page offering an amount the server
 * would refuse is the one inconsistency worth a round trip. `retry: false` so
 * the 404 an instance with donations switched off answers is not retried three
 * times before the page can say so.
 */
export function useDonationOptions() {
  return useQuery({
    queryKey: ["donation-options"],
    queryFn: getDonationOptions,
    staleTime: 0,
    gcTime: 0,
    retry: false,
  });
}

export function useCreateDonation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createDonation,
    // The donation lands in the member's own receipts the moment it is raised,
    // unpaid, so that list is stale whether or not the member goes on to pay.
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["my-receipts"] });
    },
  });
}
