"use client";

import { useMemo } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslations } from "next-intl";
import type { FieldValues } from "react-hook-form";
import type { z } from "zod";
import { createZodErrorMap } from "@/lib/i18n/zod-error-map";

/**
 * `zodResolver` with a locale-aware error map. Drop-in replacement:
 *
 *     resolver: zodResolver(schema)   →   resolver: useZodResolver(schema)
 *
 * Zod's built-in messages are English regardless of the user's locale; the map
 * swaps them for `validation.*` translations without touching the schema.
 */
export function useZodResolver<TInput extends FieldValues, TOutput>(
  schema: z.core.$ZodType<TOutput, TInput>
) {
  const t = useTranslations();
  return useMemo(
    () => zodResolver<TInput, unknown, TOutput>(schema, { error: createZodErrorMap(t) }),
    [schema, t]
  );
}
