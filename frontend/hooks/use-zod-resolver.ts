"use client";

import { useMemo } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslations } from "next-intl";
import type { FieldValues } from "react-hook-form";
import type { ParseParams } from "zod";
import { createZodErrorMap } from "@/lib/i18n/zod-error-map";

/** Structural shape of a zod 3 schema, matching what `zodResolver` accepts. */
type Zod3Schema<Output, Input> = {
  _output: Output;
  _input: Input;
  _def: { typeName: string };
};

/**
 * `zodResolver` with a locale-aware error map. Drop-in replacement:
 *
 *     resolver: zodResolver(schema)   →   resolver: useZodResolver(schema)
 *
 * Zod's built-in messages are English regardless of the user's locale; the map
 * swaps them for `validation.*` translations without touching the schema.
 */
export function useZodResolver<TInput extends FieldValues, TOutput>(
  schema: Zod3Schema<TOutput, TInput>
) {
  const t = useTranslations();
  return useMemo(
    () =>
      zodResolver<TInput, unknown, TOutput>(
        schema,
        // `zodResolver` types this as a complete `ParseParams`, but it forwards the
        // object straight to `parseAsync`, which takes a partial one.
        { errorMap: createZodErrorMap(t) } as ParseParams
      ),
    [schema, t]
  );
}
