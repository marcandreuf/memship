import { apiClient } from "@/lib/client-api";

/**
 * What this organisation asks for, and the amounts it accepts.
 *
 * `suggested_amounts` is served rather than derived in the browser: the ladder
 * is computed from the configured minimum on the same side that refuses an
 * amount outside the bounds, so the page cannot offer a figure the server
 * would then reject.
 *
 * `message` is null until an administrator writes one, and the page renders
 * around its absence rather than printing an empty heading.
 */
export interface DonationOptions {
  message: string | null;
  min_amount: number;
  max_amount: number;
  suggested_amounts: number[];
}

/** The receipt now waiting to be paid at the gateway. */
export interface DonationResult {
  receipt_id: number;
  receipt_number: string;
  receipt_status: string;
  total_amount: number;
  due_date: string | null;
}

export async function getDonationOptions(): Promise<DonationOptions> {
  return apiClient("/members/me/donations/options");
}

export async function createDonation(amount: number): Promise<DonationResult> {
  return apiClient("/members/me/donations", {
    method: "POST",
    body: JSON.stringify({ amount: amount.toFixed(2) }),
  });
}
