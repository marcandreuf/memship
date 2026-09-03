"use client";

import { useEffect, useRef } from "react";
import { refreshSession } from "../services/auth-api";

// Anything that means a person is still there. Kept cheap: the throttle below
// turns all but one of these into a single timestamp comparison, so scroll —
// the only signal a long report gives off — can be listened to safely.
const ACTIVITY_EVENTS = ["pointerdown", "keydown", "scroll"] as const;

/**
 * Renews the session cookie while the user is actually working.
 *
 * The window is an idle timeout, not a cap on the visit: the backend re-issues
 * the cookie for anyone whose current token is still valid, so activity slides
 * the deadline forward and only real inactivity ends the session. Renewal is
 * driven by the user's own events rather than a bare interval, so a tab left
 * open on a dashboard still times out on schedule.
 *
 * @param refreshAfterSeconds `session_refresh_after` from /auth/me — how far
 *   into the window the backend wants an active client to renew. Undefined
 *   until that query resolves, which disables the hook.
 */
export function useSessionRefresh(refreshAfterSeconds: number | undefined) {
  // Mounting means a full page load, which is itself activity and restarts the
  // window — so this is a true starting point, not an assumption about when the
  // session began.
  const lastRefresh = useRef(Date.now());

  useEffect(() => {
    if (!refreshAfterSeconds) return;
    const intervalMs = refreshAfterSeconds * 1000;

    function onActivity() {
      if (Date.now() - lastRefresh.current < intervalMs) return;
      // Set before awaiting: a burst of events must not fire several renewals.
      lastRefresh.current = Date.now();
      // A 401 here is a session that already died; apiClient's handler sends
      // the user to the login page, so there is nothing to do with the error.
      refreshSession().catch(() => {});
    }

    for (const event of ACTIVITY_EVENTS) {
      window.addEventListener(event, onActivity, { passive: true });
    }
    return () => {
      for (const event of ACTIVITY_EVENTS) {
        window.removeEventListener(event, onActivity);
      }
    };
  }, [refreshAfterSeconds]);
}
