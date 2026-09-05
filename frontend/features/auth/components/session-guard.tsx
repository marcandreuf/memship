"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "@/lib/i18n/routing";
import { setUnauthorizedHandler } from "@/lib/client-api";
import { useSessionRefresh } from "../hooks/use-session-refresh";

/**
 * Keeps the portal's session honest: renews it while the user works, and sends
 * them to the login page the moment it is gone.
 *
 * Mounted inside the portal only. That placement is the whole guard against
 * hijacking an expected 401 — the login form's own "wrong password" never
 * reaches a registered handler, because no handler exists on that page.
 */
export function SessionGuard({
  refreshAfterSeconds,
}: {
  refreshAfterSeconds: number | undefined;
}) {
  const queryClient = useQueryClient();
  const router = useRouter();

  useSessionRefresh(refreshAfterSeconds);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      // Clear first: the cached user is what let the portal keep rendering as
      // if signed in, and the login page must not read anything from it.
      queryClient.clear();
      router.replace("/login?expired=1");
    });
    return () => setUnauthorizedHandler(null);
  }, [queryClient, router]);

  return null;
}
