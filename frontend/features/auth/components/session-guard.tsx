"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter } from "@/lib/i18n/routing";
import { locationAsReturnTo, withNext } from "@/lib/return-to";
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
  const pathname = usePathname();

  useSessionRefresh(refreshAfterSeconds);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      // Clear first: the cached user is what let the portal keep rendering as
      // if signed in, and the login page must not read anything from it.
      queryClient.clear();
      // Where they were, so signing back in resumes the task rather than
      // restarting it (memship#598). `pathname` is a dependency because the
      // handler can fire an hour after it was registered, and a stale closure
      // would return them to whatever page they first opened. The query string
      // is read as it fires, since it changes without remounting this.
      router.replace(
        withNext("/login?expired=1", locationAsReturnTo(pathname, window.location.search)),
      );
    });
    return () => setUnauthorizedHandler(null);
  }, [queryClient, router, pathname]);

  return null;
}
