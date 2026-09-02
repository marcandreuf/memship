import { z } from "zod";

/**
 * Localised messages for zod's built-in validation failures.
 *
 * Zod ships English defaults ("String must contain at least 1 character(s)"),
 * which leak to the user whatever locale they picked. Passing this map into
 * `zodResolver(schema, { errorMap })` replaces every default with a `validation.*`
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

export function createZodErrorMap(t: ValidationTranslator): z.ZodErrorMap {
  return (issue) => {
    switch (issue.code) {
      case z.ZodIssueCode.invalid_type: {
        if (issue.received === "undefined" || issue.received === "null") {
          return { message: t("validation.required") };
        }
        if (issue.expected === "integer") {
          return { message: t("validation.notAnInteger") };
        }
        if (issue.expected === "number" || issue.expected === "bigint") {
          return { message: t("validation.notANumber") };
        }
        if (issue.expected === "date") {
          return { message: t("validation.invalidDate") };
        }
        return { message: t("validation.invalid") };
      }

      case z.ZodIssueCode.too_small: {
        const min = Number(issue.minimum);
        switch (issue.type) {
          case "string":
            // `.min(1)` is the idiom for "this field is mandatory".
            return min <= 1 && issue.inclusive
              ? { message: t("validation.required") }
              : { message: t("validation.tooShort", { min }) };
          case "array":
            return { message: t("validation.tooFewItems", { min }) };
          case "date":
            return { message: t("validation.dateTooEarly") };
          default:
            return issue.inclusive
              ? { message: t("validation.tooSmall", { min }) }
              : { message: t("validation.tooSmallExclusive", { min }) };
        }
      }

      case z.ZodIssueCode.too_big: {
        const max = Number(issue.maximum);
        switch (issue.type) {
          case "string":
            return { message: t("validation.tooLong", { max }) };
          case "array":
            return { message: t("validation.tooManyItems", { max }) };
          case "date":
            return { message: t("validation.dateTooLate") };
          default:
            return issue.inclusive
              ? { message: t("validation.tooBig", { max }) }
              : { message: t("validation.tooBigExclusive", { max }) };
        }
      }

      case z.ZodIssueCode.invalid_string: {
        if (issue.validation === "email") {
          return { message: t("validation.invalidEmail") };
        }
        if (issue.validation === "url") {
          return { message: t("validation.invalidUrl") };
        }
        if (issue.validation === "datetime" || issue.validation === "date") {
          return { message: t("validation.invalidDate") };
        }
        return { message: t("validation.invalidFormat") };
      }

      case z.ZodIssueCode.invalid_enum_value:
      case z.ZodIssueCode.invalid_literal:
        return { message: t("validation.invalidOption") };

      case z.ZodIssueCode.not_multiple_of:
        return {
          message: t("validation.notAMultipleOf", { multiple: Number(issue.multipleOf) }),
        };

      case z.ZodIssueCode.invalid_date:
        return { message: t("validation.invalidDate") };

      case z.ZodIssueCode.invalid_union: {
        // Union branches are parsed with this same map, so their messages are
        // already localised — surface the first one instead of a bare "Invalid input".
        const first = issue.unionErrors?.[0]?.issues?.[0];
        if (first?.message) return { message: first.message };
        return { message: t("validation.invalid") };
      }

      default:
        return { message: t("validation.invalid") };
    }
  };
}
