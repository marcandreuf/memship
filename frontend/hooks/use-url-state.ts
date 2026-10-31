import { parseAsInteger, parseAsString, useQueryState } from "nuqs";

/**
 * URL-persisted search query parameter (?q=...).
 * Defaults to empty string, shallow updates (no server re-render).
 */
export function useSearchParam() {
  return useQueryState("q", parseAsString.withDefault("").withOptions({ shallow: true }));
}

/**
 * URL-persisted page parameter (?page=...).
 * Defaults to 1, shallow updates.
 */
export function usePageParam() {
  return useQueryState("page", parseAsInteger.withDefault(1).withOptions({ shallow: true }));
}

/**
 * URL-persisted status filter parameter (?status=...).
 * Defaults to empty string, shallow updates.
 */
export function useStatusParam() {
  return useQueryState("status", parseAsString.withDefault("").withOptions({ shallow: true }));
}

/**
 * URL-persisted open tab parameter (?tab=...).
 * Defaults to empty string, shallow updates.
 *
 * nuqs replaces rather than pushes by default, which is what this wants: a tab
 * switch should leave the record's URL carrying the open tab so Browser Back
 * from a record opened out of that tab returns to it, without making Back walk
 * backwards through every tab that was looked at (memship#471).
 */
export function useTabParam() {
  return useQueryState("tab", parseAsString.withDefault("").withOptions({ shallow: true }));
}
