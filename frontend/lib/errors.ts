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
  if (error instanceof ClientApiError) {
    if (typeof error.detail === "string") {
      return error.detail;
    }
    if (Array.isArray(error.detail) && error.detail.length > 0) {
      return error.detail.map((d) => d.msg).join(", ");
    }
    if (isCoded(error.detail)) {
      const key = `apiErrors.${error.detail.code}`;
      if (t?.has(key)) {
        return t(key, translationValues(error.detail));
      }
      return error.detail.message ?? error.detail.code;
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
  form: UseFormReturn<T>
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
      form.setError(fieldName, { type: "server", message: item.msg });
      mapped = true;
    }
  }
  return mapped;
}
