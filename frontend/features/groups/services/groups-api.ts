import { apiClient } from "@/lib/client-api";

export interface GroupData {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  is_billable: boolean;
  display_order: number;
  color: string | null;
  icon: string | null;
  is_active: boolean;
  created_at: string;
}

export async function listGroups(): Promise<GroupData[]> {
  return apiClient("/groups");
}

export async function getGroup(id: number): Promise<GroupData> {
  return apiClient(`/groups/${id}`);
}

export async function createGroup(data: {
  name: string;
  slug: string;
  description?: string;
  is_billable?: boolean;
  color?: string;
  icon?: string;
}): Promise<GroupData> {
  return apiClient("/groups", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateGroup(
  id: number,
  data: Record<string, unknown>
): Promise<GroupData> {
  return apiClient(`/groups/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteGroup(id: number): Promise<void> {
  await apiClient(`/groups/${id}`, { method: "DELETE" });
}
