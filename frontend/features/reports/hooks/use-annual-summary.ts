import { useQuery } from "@tanstack/react-query";
import { getAnnualSummary } from "../services/reports-api";

export function useAnnualSummary(year?: number) {
  return useQuery({
    queryKey: ["annual-summary", year ?? "current"],
    queryFn: () => getAnnualSummary(year),
  });
}
