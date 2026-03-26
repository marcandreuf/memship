import { apiClient } from "@/lib/client-api";

export interface ContactTypeData {
  id: number;
  code: string;
  name: string;
}

export interface ContactData {
  id: number;
  contact_type_id: number | null;
  contact_type_name: string | null;
  value: string;
  label: string | null;
  is_primary: boolean;
}

export async function getContactTypes(): Promise<ContactTypeData[]> {
  return apiClient("/contact-types");
}

export async function getContacts(personId: number): Promise<ContactData[]> {
  return apiClient(`/persons/${personId}/contacts`);
}

export async function createContact(
  personId: number,
  data: Record<string, unknown>
): Promise<ContactData> {
  return apiClient(`/persons/${personId}/contacts`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateContact(
  contactId: number,
  data: Record<string, unknown>
): Promise<ContactData> {
  return apiClient(`/contacts/${contactId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteContact(contactId: number): Promise<void> {
  return apiClient(`/contacts/${contactId}`, { method: "DELETE" });
}
