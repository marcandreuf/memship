import { apiClient } from "@/lib/client-api";

export type CommunicationTier = "mandatory" | "operational" | "optional";

export interface CommunicationTemplateView {
  key: string;
  group: string;
  tier: CommunicationTier;
  enabled: boolean;
}

export interface CommunicationsConfigView {
  templates: CommunicationTemplateView[];
}

export interface CommunicationsConfigUpdate {
  // Sparse: only the keys present are changed.
  templates: Record<string, boolean>;
}

export async function getCommunicationsConfig(): Promise<CommunicationsConfigView> {
  return apiClient("/settings/communications");
}

export async function updateCommunicationsConfig(
  data: CommunicationsConfigUpdate
): Promise<CommunicationsConfigView> {
  return apiClient("/settings/communications", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}
