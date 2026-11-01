"use client";

import { useSearchParams } from "next/navigation";
import { usePathname } from "@/lib/i18n/routing";
import {
  RETURN_LABEL,
  RETURN_PATH,
  locationAsReturnTo,
  parseReturnTo,
  withReturnTo,
} from "@/lib/return-to";

/**
 * The validated crumb this page was opened from, or null.
 *
 * `DetailHeader` is the only intended caller: it swaps this in for the static
 * first breadcrumb, so every detail page gets a true trail without having to
 * know anything about it.
 */
export function useReturnTo() {
  const params = useSearchParams();
  return parseReturnTo(params.get(RETURN_PATH), params.get(RETURN_LABEL));
}

/**
 * Builds links out of here that can come back, labelled `label`.
 *
 * `label` is what the breadcrumb will read, so it is the name of the record or
 * list being left, not the destination. The returned function takes the target
 * path and gives it back carrying the return context.
 *
 * The current query is preserved in the return target, which is what makes a
 * filtered, paged list come back filtered and paged rather than as page one.
 */
export function useReturnToHere(label: string): (target: string) => string {
  const pathname = usePathname();
  const params = useSearchParams();
  const here = locationAsReturnTo(pathname, params.toString());
  return (target: string) => withReturnTo(target, here, label);
}
