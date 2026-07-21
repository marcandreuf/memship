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

/** One person's values, keyed by field key. Null means nothing stored yet. */
export type CustomFieldValues = Record<string, string | null>;

export async function getPersonCustomFields(
  personId: number
): Promise<CustomFieldValues> {
  return apiClient<CustomFieldValues>(`/persons/${personId}/custom-fields`);
}

export async function updatePersonCustomFields(
  personId: number,
  values: Record<string, string | boolean | null>
): Promise<CustomFieldValues> {
  return apiClient<CustomFieldValues>(`/persons/${personId}/custom-fields`, {
    method: "PUT",
    body: JSON.stringify(values),
  });
}

export async function getMyCustomFields(): Promise<CustomFieldValues> {
  return apiClient<CustomFieldValues>("/me/custom-fields");
}

export async function updateMyCustomFields(
  values: Record<string, string | boolean | null>
): Promise<CustomFieldValues> {
  return apiClient<CustomFieldValues>("/me/custom-fields", {
    method: "PUT",
    body: JSON.stringify(values),
  });
}
