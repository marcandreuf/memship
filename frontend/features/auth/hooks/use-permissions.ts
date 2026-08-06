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
      /**
       * Holds at least one permission outside the self-service namespace.
       *
       * **Not an authorization check.** It answers "is this account staff at
       * all", which is only ever the right question for choosing the *shape*
       * of a screen (the staff dashboard, the pending-approval banner). Using
       * it to decide whether a control renders hands `members.read` the same
       * UI as a full admin — every button, every admin list — and the user
       * only finds out when the save 403s. Gate on the key the endpoint
       * behind the control is guarded by: `has("activities.write")`, not this.
       */
      isStaff: [...held].some((k) => !k.startsWith("self.")),
      hasRole: (slug: string) => (user?.roles ?? []).some((r) => r.slug === slug),
    }),
    [held, isLoading, user?.roles],
  );
}
