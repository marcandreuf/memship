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
  bank_name: string | null;
  bank_iban: string | null;
  bank_bic: string | null;
  invoice_prefix: string;
  invoice_next_number: number;
  features: Record<string, unknown>;
  custom_settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AddressData {
  id: number;
  address_line1: string;
  address_line2: string | null;
  city: string;
  state_province: string | null;
  postal_code: string | null;
  country: string;
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

export async function getAddress(): Promise<AddressData | null> {
  return apiClient("/settings/address");
}

export async function updateAddress(
  data: Record<string, unknown>
): Promise<AddressData> {
  return apiClient("/settings/address", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}
