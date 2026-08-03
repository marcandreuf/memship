import { apiClient } from "@/lib/client-api";
import type { RoleSummary } from "@/features/auth/services/auth-api";

/** A catalog entry. The catalog lives in backend code, never in a table, so
 *  this is read-only — there is no create/delete for a permission. */
export interface Permission {
  key: string;
  domain: string;
  action: string;
  /** Reserved keys are rejected on any non-system role: superadmin only. */
  reserved: boolean;
  label_key: string;
  description_key: string;
}

export interface Role {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  is_system: boolean;
  permission_keys: string[];
  assigned_user_count: number;
  /** Computed by the API against the caller — never recompute it here, the
   *  server runs the super_admin rule plus the subset check. */
  assignable: boolean;
}

export interface RoleInput {
  name: string;
  description: string | null;
  permission_keys: string[];
}

export interface UserAccount {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  roles: RoleSummary[];
}

export async function listPermissions(): Promise<Permission[]> {
  return apiClient<Permission[]>("/permissions");
}

export async function listRoles(): Promise<Role[]> {
  return apiClient<Role[]>("/roles");
}

export async function createRole(data: RoleInput): Promise<Role> {
  return apiClient<Role>("/roles", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateRole(
  id: number,
  data: Partial<RoleInput>
): Promise<Role> {
  return apiClient<Role>(`/roles/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteRole(id: number): Promise<void> {
  return apiClient<void>(`/roles/${id}`, { method: "DELETE" });
}

export async function listUsers(q?: string, roleId?: number): Promise<UserAccount[]> {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (roleId !== undefined) params.set("role_id", String(roleId));
  const query = params.toString();
  return apiClient<UserAccount[]>(`/users${query ? `?${query}` : ""}`);
}

/** Full replacement. `member` is pinned server-side whether or not it is
 *  named, and an empty list is refused with `roles_required`. */
export async function updateUserRoles(
  userId: number,
  roleIds: number[]
): Promise<UserAccount> {
  return apiClient<UserAccount>(`/users/${userId}/roles`, {
    method: "PUT",
    body: JSON.stringify({ role_ids: roleIds }),
  });
}

export async function setUserActive(
  userId: number,
  isActive: boolean
): Promise<UserAccount> {
  return apiClient<UserAccount>(`/users/${userId}/active`, {
    method: "PUT",
    body: JSON.stringify({ is_active: isActive }),
  });
}
