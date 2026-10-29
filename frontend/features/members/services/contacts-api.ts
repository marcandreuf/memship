import { apiClient } from "@/lib/client-api";

export interface ContactTypeData {
  id: number;
  code: string;
  name: string;
  /** Types group into channels, and both the primary slot and the cap below
   * are per channel: phone_home and phone_mobile share one. */
  channel: string | null;
}

export interface ContactData {
  id: number;
  contact_type_id: number | null;
  contact_type_name: string | null;
  value: string;
  label: string | null;
  is_primary: boolean;
  channel: string | null;
}

/** How many contacts one party may hold in a single channel.
 *
 * A guardrail in the UI, not a database constraint: the API still accepts
 * more, so a direct call gets past it. Enforced here because this is where
 * someone adds a sixth phone number by hand. */
export const MAX_CONTACTS_PER_CHANNEL = 5;

/** The channels already at the cap. */
export function fullChannels(contacts: ContactData[]): Set<string> {
  const counts = new Map<string, number>();
  for (const contact of contacts) {
    if (!contact.channel) continue;
    counts.set(contact.channel, (counts.get(contact.channel) ?? 0) + 1);
  }
  return new Set(
    [...counts.entries()]
      .filter(([, count]) => count >= MAX_CONTACTS_PER_CHANNEL)
      .map(([channel]) => channel),
  );
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
