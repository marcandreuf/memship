import { apiClient } from "@/lib/client-api";
import type { ContactData } from "@/features/members/services/contacts-api";

export interface EntityData {
  id: number;
  kind: string;
  name: string;
  national_id: string | null;
  email: string | null;
  created_at: string | null;
}

export interface EntityKind {
  code: string;
  name: string;
}

export interface EntityAddress {
  id: number;
  address_line1: string;
  address_line2: string | null;
  city: string;
  state_province: string | null;
  postal_code: string | null;
  country: string;
}

export interface PartySearchResult {
  id: number;
  display_name: string;
  kind: string;
  national_id: string | null;
}

export interface PaginatedEntities {
  items: EntityData[];
  meta: {
    page: number;
    per_page: number;
    total: number;
    total_pages: number;
  };
}

export async function getEntities(params?: URLSearchParams): Promise<PaginatedEntities> {
  return apiClient(`/entities${params ? `?${params}` : ""}`);
}

export async function getEntity(id: number): Promise<EntityData> {
  return apiClient(`/entities/${id}`);
}

export async function getEntityKinds(): Promise<EntityKind[]> {
  return apiClient("/entities/kinds");
}

export async function createEntity(data: Record<string, unknown>): Promise<EntityData> {
  return apiClient("/entities", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateEntity(id: number, data: Record<string, unknown>): Promise<EntityData> {
  return apiClient(`/entities/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteEntity(id: number): Promise<void> {
  return apiClient(`/entities/${id}`, { method: "DELETE" });
}

export async function getEntityAddress(id: number): Promise<EntityAddress | null> {
  return apiClient(`/entities/${id}/address`);
}

export async function updateEntityAddress(
  id: number,
  data: Record<string, unknown>
): Promise<EntityAddress> {
  return apiClient(`/entities/${id}/address`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function searchParties(q: string): Promise<PartySearchResult[]> {
  return apiClient(`/parties/search?q=${encodeURIComponent(q)}`);
}

export async function getEntityContacts(partyId: number): Promise<ContactData[]> {
  return apiClient(`/parties/${partyId}/contacts`);
}

export async function createEntityContact(
  partyId: number,
  data: Record<string, unknown>
): Promise<ContactData> {
  return apiClient(`/parties/${partyId}/contacts`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}
