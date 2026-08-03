"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createRole,
  deleteRole,
  listPermissions,
  listRoles,
  listUsers,
  setUserActive,
  updateRole,
  updateUserRoles,
  type RoleInput,
} from "../services/roles-api";

/** The whole roles API 404s while `features.custom_roles` is off — pass
 *  `enabled` from the flag rather than letting every screen retry a 404. */
export function usePermissionCatalog(enabled = true) {
  return useQuery({
    queryKey: ["permissions"],
    queryFn: listPermissions,
    enabled,
    // The catalog is a code constant; it cannot change while the tab is open.
    staleTime: Infinity,
  });
}

export function useRoles(enabled = true) {
  return useQuery({ queryKey: ["roles"], queryFn: listRoles, enabled });
}

export function useCreateRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createRole,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["roles"] }),
  });
}

export function useUpdateRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<RoleInput> }) =>
      updateRole(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["roles"] });
      // Retuning a role changes what its holders can do, and the sidebar
      // renders from /auth/me — refetch it rather than wait for a focus event.
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
    },
  });
}

export function useDeleteRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteRole,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["roles"] }),
  });
}

export function useUserAccounts(q?: string, roleId?: number, enabled = true) {
  return useQuery({
    queryKey: ["user-accounts", q ?? "", roleId ?? null],
    queryFn: () => listUsers(q, roleId),
    enabled,
  });
}

export function useUpdateUserRoles() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, roleIds }: { userId: number; roleIds: number[] }) =>
      updateUserRoles(userId, roleIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-accounts"] });
      // assigned_user_count moves with every assignment.
      queryClient.invalidateQueries({ queryKey: ["roles"] });
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
    },
  });
}

export function useSetUserActive() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, isActive }: { userId: number; isActive: boolean }) =>
      setUserActive(userId, isActive),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["user-accounts"] }),
  });
}