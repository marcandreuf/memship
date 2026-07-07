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
