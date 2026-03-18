import { apiClient } from "@/lib/client-api";

export interface PersonData {
  id: number;
  first_name: string;
  last_name: string;
  email: string | null;
  date_of_birth: string | null;
  gender: string | null;
  national_id: string | null;
  photo_url: string | null;
}

export interface MemberData {
  id: number;
  person_id: number;
  person: PersonData;
  membership_type_id: number | null;
  membership_type_name: string | null;
  member_number: string | null;
  status: string;
  status_reason: string | null;
  joined_at: string;
  internal_notes: string | null;
  is_active: boolean;
  created_at: string;
}

export interface PageMeta {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

export interface PaginatedMembers {
  items: MemberData[];
  meta: PageMeta;
}

export interface MembershipTypeData {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  base_price: number;
  billing_frequency: string;
  group_id: number | null;
  group_name: string | null;
  is_active: boolean;
  created_at: string;
}

export interface ListMembersParams {
  page?: number;
  per_page?: number;
  search?: string;
  status?: string;
}

export async function listMembers(
  params: ListMembersParams = {}
): Promise<PaginatedMembers> {
  const searchParams = new URLSearchParams();
  if (params.page) searchParams.set("page", String(params.page));
  if (params.per_page) searchParams.set("per_page", String(params.per_page));
  if (params.search) searchParams.set("search", params.search);
  if (params.status) searchParams.set("status", params.status);

  const qs = searchParams.toString();
  return apiClient(`/members${qs ? `?${qs}` : ""}`);
}

export async function getMember(id: number): Promise<MemberData> {
  return apiClient(`/members/${id}`);
}

export async function createMember(data: {
  first_name: string;
  last_name: string;
  email?: string;
  date_of_birth?: string;
  gender?: string;
  national_id?: string;
  membership_type_id?: number;
  internal_notes?: string;
}): Promise<MemberData> {
  return apiClient("/members", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateMember(
  id: number,
  data: Record<string, unknown>
): Promise<MemberData> {
  return apiClient(`/members/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteMember(id: number): Promise<void> {
  await apiClient(`/members/${id}`, { method: "DELETE" });
}

export async function changeMemberStatus(
  id: number,
  status: string,
  reason?: string
): Promise<MemberData> {
  return apiClient(`/members/${id}/status`, {
    method: "PUT",
    body: JSON.stringify({ status, reason }),
  });
}

export async function listMembershipTypes(): Promise<MembershipTypeData[]> {
  return apiClient("/membership-types");
}

export async function updateMembershipType(
  id: number,
  data: Record<string, unknown>
): Promise<MembershipTypeData> {
  return apiClient(`/membership-types/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteMembershipType(id: number): Promise<void> {
  await apiClient(`/membership-types/${id}`, { method: "DELETE" });
}

export async function createMembershipType(data: {
  name: string;
  slug: string;
  description?: string;
  base_price?: number;
  billing_frequency?: string;
  group_id?: number;
}): Promise<MembershipTypeData> {
  return apiClient("/membership-types", {
    method: "POST",
    body: JSON.stringify(data),
  });
}
