import { apiClient } from "@/lib/client-api";

export type CustomFieldType =
  | "text"
  | "textarea"
  | "number"
  | "date"
  | "boolean"
  | "select";

/** What a member may do with their own value. */
export type MemberAccess = "hidden" | "read" | "write";
/** What an admin may do; they always read. Super admin always writes. */
export type AdminAccess = "read" | "write";

export interface CustomFieldOption {
  value: string;
  label: string;
}

export interface CustomFieldDefinition {
  id: number;
  key: string;
  field_type: CustomFieldType;
  label: string;
  labels: Record<string, string>;
  help_text: string | null;
  options: CustomFieldOption[] | null;
  required: boolean;
  member_access: MemberAccess;
  admin_access: AdminAccess;
  sort_order: number;
  active: boolean;
  /** Resolved by the API for the current user — don't recompute it here. */
  writable: boolean;
}

export interface CustomFieldDefinitionInput {
  key?: string;
  field_type?: CustomFieldType;
  label: string;
  labels: Record<string, string>;
  help_text: string | null;
  options?: CustomFieldOption[] | null;
  required: boolean;
  member_access: MemberAccess;
  admin_access: AdminAccess;
  sort_order: number;
  active: boolean;
}

export async function listCustomFields(
  includeInactive = false
): Promise<CustomFieldDefinition[]> {
  const query = includeInactive ? "?include_inactive=true" : "";
  return apiClient<CustomFieldDefinition[]>(`/custom-fields${query}`);
}

export async function createCustomField(
  data: CustomFieldDefinitionInput
): Promise<CustomFieldDefinition> {
  return apiClient<CustomFieldDefinition>("/custom-fields", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateCustomField(
  id: number,
  data: Partial<CustomFieldDefinitionInput>
): Promise<CustomFieldDefinition> {
  return apiClient<CustomFieldDefinition>(`/custom-fields/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteCustomField(id: number): Promise<void> {
  return apiClient<void>(`/custom-fields/${id}`, { method: "DELETE" });
}
