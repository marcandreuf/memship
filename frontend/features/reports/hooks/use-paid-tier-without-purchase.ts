import { useQuery } from "@tanstack/react-query";
import { getPaidTierWithoutPurchase } from "../services/reports-api";

export function usePaidTierWithoutPurchase(page: number) {
  return useQuery({
    queryKey: ["paid-tier-without-purchase", page],
    queryFn: () => getPaidTierWithoutPurchase(page),
  });
}
