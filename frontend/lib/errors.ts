import type { UseFormReturn, FieldValues, Path } from "react-hook-form";
import {
  ClientApiError,
  type CodedErrorDetail,
  type ValidationErrorDetail,
} from "./client-api";

/** The slice of next-intl's `t` that error rendering needs. */
export type ErrorTranslator = {
  (key: string, values?: Record<string, string | number>): string;
  has: (key: string) => boolean;
};

function isCoded(detail: unknown): detail is CodedErrorDetail {
  return (
    typeof detail === "object" &&
    detail !== null &&
    !Array.isArray(detail) &&
    typeof (detail as CodedErrorDetail).code === "string"
  );
}

/**
 * The text for one 422 field error. FastAPI's validation errors carry a `type`
 * — Pydantic's own (`string_too_short`) or one a custom validator chose
 * (`invalid_iban`) — so a hand-written rule can be translated by keying on it,
 * the same way a coded error body is.
 *
 * Without a translation the backend's `msg` is shown, which is why validators
 * that matter should raise `PydanticCustomError` with a real message rather
 * than a bare `ValueError`: the latter arrives prefixed `Value error, ` and a
 * failed `pattern=` arrives as the regex itself (#377).
 */
function describeFieldError(
  item: ValidationErrorDetail,
  t?: ErrorTranslator
): string {
  const key = `apiErrors.${item.type}`;
  if (item.type && t?.has(key)) return t(key);
  return item.msg;
}

/**
 * A coded error's fields as ICU values. A list becomes a joined string plus a
 * `<key>_count`, so a translation can say "(on 3 May, 10 May)" or nothing.
 */
function translationValues(detail: CodedErrorDetail): Record<string, string | number> {
  const values: Record<string, string | number> = {};
  for (const [key, value] of Object.entries(detail)) {
    if (Array.isArray(value)) {
      values[key] = value.join(", ");
      values[`${key}_count`] = value.length;
    } else if (typeof value === "string" || typeof value === "number") {
      values[key] = value;
    }
  }
  return values;
}

/**
 * The text to show for a failed request. With `t`, a coded error is rendered
 * from `apiErrors.<code>` in the user's language; without it, or for a code
 * with no translation yet, the backend's English message is shown.
 */
export function getErrorMessage(error: unknown, t?: ErrorTranslator): string {
  const message = describeError(error, t);
  // Never hand back nothing. `client-api` falls back to `res.statusText` when a
  // body carries no `detail`, and HTTP/2 dropped the reason phrase — so behind
  // Caddy that is the empty string for every response. An empty message is a
  // toast sonner declines to render, which turns a failed save into silence.
  // The generic text is a poor message; no message is a bug.
  if (message.trim()) return message;
  return t ? t("toast.error.generic") : "An unexpected error occurred";
}

function describeError(error: unknown, t?: ErrorTranslator): string {
  if (error instanceof ClientApiError) {
    if (typeof error.detail === "string") {
      return error.detail;
    }
    if (Array.isArray(error.detail) && error.detail.length > 0) {
      return (error.detail as ValidationErrorDetail[])
        .map((d) => describeFieldError(d, t))
        .join(", ");
    }
    if (isCoded(error.detail)) {
      const key = `apiErrors.${error.detail.code}`;
      if (t?.has(key)) {
        return t(key, translationValues(error.detail));
      }
      // A code with neither a translation nor a message is a developer
      // identifier, not something to show a member.
      if (error.detail.message) return error.detail.message;
      return t ? t("toast.error.generic") : error.detail.code;
    }
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "An unexpected error occurred";
}

export function mapApiErrorsToForm<T extends FieldValues>(
  error: unknown,
  form: UseFormReturn<T>,
  t?: ErrorTranslator
): boolean {
  if (!(error instanceof ClientApiError) || error.status !== 422) {
    return false;
  }
  if (!Array.isArray(error.detail)) {
    return false;
  }

  let mapped = false;
  for (const item of error.detail as ValidationErrorDetail[]) {
    const fieldParts = item.loc.filter(
      (part) => part !== "body" && part !== "query" && part !== "path"
    );
    if (fieldParts.length > 0) {
      const fieldName = fieldParts.join(".") as Path<T>;
      // `t` is optional because most callers map fields whose backend message
      // is already adequate. Pass it where a field has a coded validator —
      // the organisation's IBAN and creditor id now do (#393), and without a
      // translator they would reach the administrator as Pydantic's own
      // English on a screen that may be running in Catalan (#377).
      form.setError(fieldName, {
        type: "server",
        message: describeFieldError(item, t),
      });
      mapped = true;
    }
  }
  return mapped;
}
