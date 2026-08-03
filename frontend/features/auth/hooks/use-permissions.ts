"use client";

import { useMemo } from "react";
import { useAuth } from "./use-auth";

export function usePermissions() {
  const { user, isLoading } = useAuth();

  const held = useMemo(
    () => new Set(user?.permissions ?? []),
    [user?.permissions],
  );

  return useMemo(
    () => ({
      isLoading,
      has: (key: string) => held.has(key),
      hasAny: (...keys: string[]) => keys.some((k) => held.has(k)),
      hasAll: (...keys: string[]) => keys.every((k) => held.has(k)),
      /** Staff hold at least one permission outside the self-service namespace. */
      isStaff: [...held].some((k) => !k.startsWith("self.")),
      hasRole: (slug: string) => (user?.roles ?? []).some((r) => r.slug === slug),
    }),
    [held, isLoading, user?.roles],
  );
}
