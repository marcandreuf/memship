/**
 * Where a detail page was opened from, carried in the URL.
 *
 * A record has more than one parent: a receipt is reachable from a member,
 * from an entity and from the receipts list, so no hardcoded first breadcrumb
 * can be correct, and every detail page hardcoded one. Opening a record from
 * another record's tab was therefore a one-way trip, with the breadcrumb
 * naming a parent the user had not come through (memship#471).
 *
 * The navigating side appends where it is and what to call it; `DetailHeader`
 * swaps that in for the static first crumb. The breadcrumb becomes the way
 * back, so no second control is added, and one mechanism covers every path in
 * including a list that was filtered and paged.
 *
 * Paths here are locale-less. `Link` and `useRouter` come from
 * `@/lib/i18n/routing`, which adds the prefix, so storing `/en/entities/376`
 * would resolve as `/en/en/entities/376`.
 */

export const RETURN_PATH = "from";
export const RETURN_LABEL = "fromLabel";

/** Longer than any real record name, short enough not to wreck the trail. */
const MAX_LABEL = 120;

/**
 * Is this a path within the app, safe to render as a link href?
 *
 * The value arrives from the query string, so it is attacker-supplied in a
 * crafted link. Rendering it unchecked turns the breadcrumb into an open
 * redirect, and `javascript:` into something worse.
 */
export function isInternalPath(value: string): boolean {
  // One leading slash exactly. `//evil.com` is protocol-relative and would
  // leave the site; `https://evil.com` and `javascript:alert(1)` have no
  // leading slash at all.
  if (!value.startsWith("/") || value.startsWith("//")) return false;
  // Some browsers normalise a backslash to a slash, so `/\evil.com` can read
  // as protocol-relative after normalisation.
  if (value.includes("\\")) return false;
  // Control characters, which can be used to smuggle a scheme past a naive
  // check, and a fragment, which is meaningless in a return target.
  if (/[\u0000-\u001f\u007f]/.test(value)) return false;
  if (value.includes("#")) return false;
  return true;
}

/**
 * The query string that records a return to `path`, labelled `label`.
 * Empty when either half is unusable, so a caller can append it blindly.
 */
export function returnToQuery(path: string, label: string): string {
  const trimmed = label.trim();
  if (!trimmed || !isInternalPath(path)) return "";
  const params = new URLSearchParams();
  params.set(RETURN_PATH, path);
  params.set(RETURN_LABEL, trimmed.slice(0, MAX_LABEL));
  return params.toString();
}

/** `target` with the return context appended, preserving any query it has. */
export function withReturnTo(target: string, path: string, label: string): string {
  const query = returnToQuery(path, label);
  if (!query) return target;
  return `${target}${target.includes("?") ? "&" : "?"}${query}`;
}

/**
 * The validated return crumb, or null when there is none to trust.
 *
 * Both halves are required: a path with no label cannot be rendered, and a
 * label with no path is not a link.
 */
export function parseReturnTo(
  path: string | null | undefined,
  label: string | null | undefined,
): { href: string; label: string } | null {
  if (!path || !label) return null;
  if (!isInternalPath(path)) return null;
  const trimmed = label.trim();
  if (!trimmed) return null;
  return { href: path, label: trimmed.slice(0, MAX_LABEL) };
}

/**
 * The current location as a return target: path plus its query, with any
 * inherited return context removed.
 *
 * Without the strip, navigating two levels in would nest one `from` inside the
 * next and the URL would grow with every hop.
 */
export function locationAsReturnTo(
  pathname: string,
  search: URLSearchParams | string,
): string {
  const params = new URLSearchParams(search);
  params.delete(RETURN_PATH);
  params.delete(RETURN_LABEL);
  const query = params.toString();
  return query ? `${pathname}?${query}` : pathname;
}
