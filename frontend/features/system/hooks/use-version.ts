"use client";

import { useQuery } from "@tanstack/react-query";

import { getHealth } from "../services/system-api";

export function useVersion() {
  return useQuery({
    queryKey: ["system", "health"],
    queryFn: getHealth,
    staleTime: 5 * 60_000,
    retry: false,
  });
}
