import { apiClient } from "@/lib/client-api";

export type HealthInfo = {
  status: string;
  version: string;
  environment: string;
};

export function getHealth() {
  return apiClient<HealthInfo>("/health");
}
