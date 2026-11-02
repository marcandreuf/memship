import type { z } from "zod";

/**
 * Localised messages for zod's built-in validation failures.
 *
 * Zod ships English defaults ("Too small: expected string to have >=1 characters"),
 * which leak to the user whatever locale they picked. Passing this map into
 * `zodResolver(schema, { error })` replaces every default with a `validation.*`
 * message, so the ~200 validators across the app need no per-schema changes.
 *
 * Issues that carry their own `message` bypass this map entirely — those pass a
 * `validation.*` key instead and are resolved at render time by
 * `useTranslateFormError`.
 */

/** The subset of next-intl's translator this module needs. */
export type ValidationTranslator = (
  key: string,
  values?: Record<string, string | number>
) => string;

export function createZodErrorMap(t: ValidationTranslator): z.core.$ZodErrorMap {
  return (issue) => {
    switch (issue.code) {
      case "invalid_type": {
        if (issue.input === undefined || issue.input === null) {
          return t("validation.required");
        }
        if (issue.expected === "int") {
          return t("validation.notAnInteger");
        }
        if (issue.expected === "number" || issue.expected === "bigint") {
          return t("validation.notANumber");
        }
        if (issue.expected === "date") {
          return t("validation.invalidDate");
        }
        return t("validation.invalid");
      }

      case "too_small": {
        const min = Number(issue.minimum);
        switch (issue.origin) {
          case "string":
            // `.min(1)` is the idiom for "this field is mandatory".
            return min <= 1 && issue.inclusive
              ? t("validation.required")
              : t("validation.tooShort", { min });
          case "array":
            return t("validation.tooFewItems", { min });
          case "date":
            return t("validation.dateTooEarly");
          default:
            return issue.inclusive
              ? t("validation.tooSmall", { min })
              : t("validation.tooSmallExclusive", { min });
        }
      }

      case "too_big": {
        const max = Number(issue.maximum);
        switch (issue.origin) {
          case "string":
            return t("validation.tooLong", { max });
          case "array":
            return t("validation.tooManyItems", { max });
          case "date":
            return t("validation.dateTooLate");
          default:
            return issue.inclusive
              ? t("validation.tooBig", { max })
              : t("validation.tooBigExclusive", { max });
        }
      }

      case "invalid_format": {
        if (issue.format === "email") {
          return t("validation.invalidEmail");
        }
        if (issue.format === "url") {
          return t("validation.invalidUrl");
        }
        if (issue.format === "datetime" || issue.format === "date") {
          return t("validation.invalidDate");
        }
        return t("validation.invalidFormat");
      }

      case "invalid_value":
        return t("validation.invalidOption");

      case "not_multiple_of":
        return t("validation.notAMultipleOf", { multiple: Number(issue.divisor) });

      case "invalid_union": {
        // Union branches are parsed with this same map, so their messages are
        // already localised — surface the first one instead of a bare "Invalid input".
        const first = issue.errors?.[0]?.[0];
        if (first?.message) return first.message;
        return t("validation.invalid");
      }

      default:
        return t("validation.invalid");
    }
  };
}
