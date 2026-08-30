/**
 * Which permission a portal route needs, for the layout's redirect guard.
 *
 * The server is the authority — every endpoint behind these pages is guarded
 * independently, and this map cannot grant anything. It exists so that typing
 * a URL you have no permission for lands you somewhere sensible instead of on
 * a shell that renders empty tables and 403s on every click.
 *
 * Longest matching prefix wins, so `/members/pending` is checked against
 * `members.approve` rather than inheriting `/members`. A route absent from the
 * list is open to any authenticated account.
 */
export const ROUTE_PERMISSIONS: ReadonlyArray<readonly [string, readonly string[]]> = [
  // The `/new` forms are the write surface of their list, so they take the
  // write key — hiding the button is not enough, the URL is typeable.
  ["/members/new", ["members.write"]],
  ["/members/pending", ["members.approve"]],
  ["/members", ["members.read"]],
  ["/activities/new", ["activities.write"]],
  ["/communications/new", ["communications.write"]],
  ["/groups", ["membership.read"]],
  ["/scan", ["members.read"]],
  ["/spaces", ["bookings.read"]],
  ["/receipts", ["billing.read"]],
  ["/mandates", ["billing.read"]],
  ["/remittances", ["billing.read"]],
  ["/billing-runs", ["billing.read"]],
  ["/annual-summary", ["reports.read"]],
  ["/communications", ["communications.read"]],
  // Settings is a bag of tabs with their own gates — membership types is
  // reachable on `membership.write` alone, so any one of these opens the page.
  [
    "/settings",
    [
      "settings.read",
      "membership.write",
      "roles.read",
      "users.read",
      "settings.custom_fields.write",
    ],
  ],
  // Member-facing routes. Everyone holds these today because `member` is
  // pinned to every account, but the keys are what the pages actually need.
  ["/activities", ["self.activities.read", "activities.read"]],
  ["/announcements", ["self.communications.read"]],
  ["/book", ["self.bookings.write"]],
  ["/my-activities", ["self.registrations.read"]],
  ["/my-bookings", ["self.bookings.read"]],
  ["/my-receipts", ["self.billing.read"]],
  ["/my-card", ["self.card.read"]],
  ["/profile", ["self.profile.read"]],
];

/**
 * Routes that also need an org `features` flag switched on.
 *
 * Same longest-prefix rule. A feature switched off 404s its endpoints, so
 * without this the page renders a shell over a dead API instead of redirecting.
 */
export const ROUTE_FEATURES: ReadonlyArray<readonly [string, string]> = [
  ["/communications", "communications"],
  ["/announcements", "communications"],
];

/** The keys that open `pathname`, or `null` when the route is unrestricted. */
export function requiredPermissions(pathname: string): readonly string[] | null {
  let match: readonly string[] | null = null;
  let matchedPrefix = "";

  for (const [prefix, keys] of ROUTE_PERMISSIONS) {
    const hit = pathname === prefix || pathname.startsWith(prefix + "/");
    if (hit && prefix.length > matchedPrefix.length) {
      match = keys;
      matchedPrefix = prefix;
    }
  }

  return match;
}

/** The `features` key `pathname` needs, or `null` when it is not feature-gated. */
export function requiredFeature(pathname: string): string | null {
  let match: string | null = null;
  let matchedPrefix = "";

  for (const [prefix, key] of ROUTE_FEATURES) {
    const hit = pathname === prefix || pathname.startsWith(prefix + "/");
    if (hit && prefix.length > matchedPrefix.length) {
      match = key;
      matchedPrefix = prefix;
    }
  }

  return match;
}