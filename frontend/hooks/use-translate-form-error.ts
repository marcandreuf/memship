"use client";

import { useCallback } from "react";
import { useTranslations } from "next-intl";

const VALIDATION_PREFIX = "validation.";

/**
 * Resolves a react-hook-form error message for display.
 *
 * Zod skips the resolver's error map for any issue that carries its own
 * `message`, so `.refine()` / `.superRefine()` / `.regex()` messages pass a
 * `validation.*` key instead of literal text and are translated here. Anything
 * else — server-set messages from `mapApiErrorsToForm`, third-party strings —
 * is rendered unchanged.
 */
export function useTranslateFormError() {
  const t = useTranslations();

  return useCallback(
    (message: unknown): string => {
      if (typeof message !== "string" || !message) return "";
      if (!message.startsWith(VALIDATION_PREFIX)) return message;
      return t.has(message) ? t(message) : message;
    },
    [t]
  );
}
