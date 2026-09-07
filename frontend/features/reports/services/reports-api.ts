import { apiClient } from "@/lib/client-api";

export interface ActivityParticipation {
  activity_name: string;
  count: number;
}

export interface AnnualSummary {
  year: number;
  revenue_by_month: number[];
  outstanding_by_month: number[];
  new_members_by_month: number[];
  active_members: number;
  total_members: number;
  new_members: number;
  lost_members: number;
  net_growth: number;
  activity_participation: ActivityParticipation[];
}

export function getAnnualSummary(year?: number): Promise<AnnualSummary> {
  const qs = year ? `?year=${year}` : "";
  return apiClient<AnnualSummary>(`/reports/annual-summary${qs}`);
}

export interface PaidTierMember {
  member_id: number;
  member_number: string | null;
  full_name: string;
  email: string | null;
  status: string;
  joined_at: string;
  membership_type_id: number;
  membership_type_name: string;
  base_price: number;
  billing_frequency: string;
  unpaid_receipts: number;
  unpaid_amount: number;
}

export interface PaidTierWithoutPurchase {
  meta: { page: number; per_page: number; total: number; total_pages: number };
  items: PaidTierMember[];
}

export function getPaidTierWithoutPurchase(
  page = 1
): Promise<PaidTierWithoutPurchase> {
  return apiClient<PaidTierWithoutPurchase>(
    `/reports/paid-tier-without-purchase?page=${page}`
  );
}
