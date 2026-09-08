import { apiClient } from "@/lib/client-api";

/**
 * What a plan costs this member today.
 *
 * `total_amount` is the figure to show. Never derive it in the browser from
 * `full_price` and a rate: VAT comes from the `membership-{slug}` concept,
 * which an admin can edit, and the plan's stored price is a base amount the
 * receipt then contradicts.
 *
 * `months_charged` / `months_in_period` are null for a `one_time` plan, which
 * has no calendar period and is never prorated.
 */
export interface MembershipQuoteData {
  membership_type_id: number;
  membership_type_name: string;
  billing_frequency: string;
  full_price: number;
  base_amount: number;
  vat_rate: number;
  vat_amount: number;
  total_amount: number;
  is_prorated: boolean;
  period_start: string | null;
  period_end: string | null;
  months_charged: number | null;
  months_in_period: number | null;
}

/** A quote, plus the receipt the purchase raised. */
export interface MembershipPurchaseData extends MembershipQuoteData {
  receipt_id: number;
  receipt_number: string;
  receipt_status: string;
  due_date: string | null;
}

export async function getMembershipQuote(
  membershipTypeId: number
): Promise<MembershipQuoteData> {
  return apiClient(`/members/me/membership/quote/${membershipTypeId}`);
}

export async function purchaseMembership(
  membershipTypeId: number
): Promise<MembershipPurchaseData> {
  return apiClient("/members/me/membership/purchase", {
    method: "POST",
    body: JSON.stringify({ membership_type_id: membershipTypeId }),
  });
}
