"use client";

import { useTranslations } from "next-intl";
import type { ProviderConfigError } from "../services/payment-providers-api";

/**
 * Turns a provider validation error into a sentence in the viewer's language.
 *
 * The backend sends a code and its parameters rather than a rendered message,
 * because the organization may not be running in English (#223). Both halves of
 * the sentence live in the locale files: the rule, and the field's name.
 *
 * A rule or field with no translation yet falls back to its key, so adding a
 * provider field reads badly rather than breaking the settings screen.
 */
export function useProviderErrors() {
  const t = useTranslations();

  function fieldLabel(key: string | undefined): string {
    if (!key) return "";
    const path = `settings.providers.fields.${key}`;
    return t.has(path) ? t(path) : key;
  }

  function describe(error: ProviderConfigError): string {
    const path = `settings.providers.errors.${error.code}`;
    if (!t.has(path)) return error.code;
    return t(path, {
      field: fieldLabel(error.field),
      prefix: error.prefix ?? "",
      length: error.length ?? 0,
      min: error.min ?? 0,
      max: error.max ?? 0,
      options: (error.options ?? []).join(", "),
      provider_type: error.provider_type ?? "",
    });
  }

  function describeAll(errors: ProviderConfigError[] | undefined): string {
    return (errors ?? []).map(describe).join("; ");
  }

  return { describe, describeAll, fieldLabel };
}
