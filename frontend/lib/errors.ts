import type { UseFormReturn, FieldValues, Path } from "react-hook-form";
import { ClientApiError, type ValidationErrorDetail } from "./client-api";

export function getErrorMessage(error: unknown): string {
  if (error instanceof ClientApiError) {
    if (typeof error.detail === "string") {
      return error.detail;
    }
    if (Array.isArray(error.detail) && error.detail.length > 0) {
      return error.detail.map((d) => d.msg).join(", ");
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
