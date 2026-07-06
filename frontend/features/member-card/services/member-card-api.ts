import { apiClient } from "@/lib/client-api";

export interface CardOrganization {
  name: string;
  logo_url: string | null;
  brand_color: string | null;
}

export interface CardData {
  member_id: number;
  full_name: string;
  member_number: string;
  status: string;
  photo_url: string | null;
  organization: CardOrganization;
  token: string;
}

export interface AssignNumbersResult {
  assigned: number;
}

export interface ScanResult {
  member_id: number;
  full_name: string;
  member_number: string;
  status: string;
  photo_url: string | null;
}

export async function getMyCard(): Promise<CardData> {
  return apiClient("/me/card");
}

export async function getMemberCard(memberId: number): Promise<CardData> {
  return apiClient(`/members/${memberId}/card`);
}

export async function assignMemberNumbers(): Promise<AssignNumbersResult> {
  return apiClient("/members/assign-numbers", { method: "POST" });
}

export async function scanCard(token: string): Promise<ScanResult> {
  return apiClient("/card/scan", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}
