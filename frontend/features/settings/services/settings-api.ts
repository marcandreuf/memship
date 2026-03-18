import { apiClient } from "@/lib/client-api";

export interface SettingsData {
  id: number;
  name: string;
  legal_name: string | null;
  email: string | null;
  phone: string | null;
  website: string | null;
  logo_url: string | null;
  tax_id: string | null;
  locale: string;
  timezone: string;
  currency: string;
  date_format: string;
  brand_color: string | null;
  features: Record<string, unknown>;
  custom_settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export async function getSettings(): Promise<SettingsData> {
  return apiClient("/settings");
}

export async function updateSettings(
  data: Record<string, unknown>
): Promise<SettingsData> {
  return apiClient("/settings", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}
