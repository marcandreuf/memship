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
