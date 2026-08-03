import { ClientApiError } from "@/lib/client-api";
import type { Permission } from "../services/roles-api";

/** The catalog's `domain` is the key minus its last segment, so
 *  `settings.custom_fields.write` reports `settings.custom_fields` and every
 *  self-service key reports `self.<area>`. For the editor we want one box per
 *  area: fold the administrative ones back to their top-level domain, and keep
 *  the self-service ones split by area so they don't collapse into one.
 *
 *  The separator is `_`, not `.`: these ids are interpolated into the message
 *  path `roles.domains.<id>`, and next-intl reads a dot as a nesting level. */
export function groupKey(permission: Permission): string {
  const parts = permission.domain.split(".");
  return parts[0] === "self" ? `self_${parts[1]}` : parts[0];
}

export function isSelfServiceGroup(key: string): boolean {
  return key.startsWith("self_");
}

export type PermissionGroup = [string, Permission[]];

/** Catalog order is meaningful (it reads members → billing → settings), so
 *  groups come out in first-seen order rather than alphabetically. */
export function groupPermissions(catalog: Permission[]): {
  administrative: PermissionGroup[];
  selfService: PermissionGroup[];
} {
  const administrative = new Map<string, Permission[]>();
  const selfService = new Map<string, Permission[]>();

  for (const permission of catalog) {
    const key = groupKey(permission);
    const target = isSelfServiceGroup(key) ? selfService : administrative;
    const bucket = target.get(key);
    if (bucket) bucket.push(permission);
    else target.set(key, [permission]);
  }

  return {
    administrative: [...administrative.entries()],
    selfService: [...selfService.entries()],
  };
}

/** The roles API returns structured `detail` objects (`{code, ...}`) rather
 *  than the plain strings `ClientApiError` is typed for. */
export function errorDetail(
  error: unknown
): (Record<string, unknown> & { code?: string }) | null {
  if (!(error instanceof ClientApiError)) return null;
  const detail = error.detail as unknown;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    return detail as Record<string, unknown> & { code?: string };
  }
  return null;
}
