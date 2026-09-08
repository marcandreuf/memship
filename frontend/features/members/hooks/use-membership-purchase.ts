"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getMembershipQuote,
  purchaseMembership,
} from "../services/membership-purchase-api";

/**
 * Price a plan for the signed-in member.
 *
 * Not cached: the quote is prorated against today's date and the concept's VAT
 * rate, both of which can move under a page left open.
 */
export function useMembershipQuote(membershipTypeId: number | null) {
  return useQuery({
    queryKey: ["membership-quote", membershipTypeId],
    queryFn: () => getMembershipQuote(membershipTypeId!),
    enabled: membershipTypeId != null,
    staleTime: 0,
    gcTime: 0,
    retry: false,
  });
}

export function usePurchaseMembership() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: purchaseMembership,
    // A purchase raises one receipt and voids any other still awaiting
    // payment, so the member's receipt list is stale either way.
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["my-receipts"] });
      qc.invalidateQueries({ queryKey: ["members"] });
    },
  });
}
