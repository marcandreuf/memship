import { z } from "zod";

/**
 * An email address, normalised the way the backend stores it.
 *
 * The transforms come before `.email()` deliberately: Zod applies string
 * checks in the order they are chained, and its email pattern is anchored, so
 * `.email().trim()` rejects a pasted `"  a@b.com  "` before the trim can help.
 * The backend accepts and normalises that input, which left the form the
 * stricter of the two and failed a paste for no reason a user could see.
 *
 * Lower-casing matches what is written to the database, so a field does not
 * appear to change by itself when the saved value is read back.
 */
export const emailSchema = z.string().trim().toLowerCase().email().max(255);

/** The same address where the form allows an empty field. */
export const optionalEmailSchema = emailSchema.optional().or(z.literal(""));

/**
 * An optional whole number for a form field a user may leave empty.
 *
 * The `.optional().or(z.literal(""))` idiom used by `optionalEmailSchema` above
 * does **not** transfer to numbers, and the difference is the whole bug behind
 * #542. That idiom works for an email because `emailSchema` *rejects* `""`, so
 * the union moves on and the empty-string branch is reached. `z.coerce.number()`
 * instead *succeeds* on `""`, coercing it to `0` — so the first branch always
 * matched, the literal branch was dead code, and the guard that followed tested
 * for a `""` that no longer existed. An emptied field arrived as a real `0`:
 * an invalid foreign key for `modality_id`, which answered 500, and a stated
 * age restriction where the user meant none.
 *
 * Empty parses to `undefined` instead, which is what the submit handlers
 * already test for, so an emptied field sends `null` or is omitted rather than
 * sending zero. Pass the same `min`/`max` the field had: a bound that excludes
 * zero is no longer what keeps the field honest, but it is still the bound.
 */
export function optionalNumber(opts: { min?: number; max?: number } = {}) {
  let num = z.coerce.number<number>().int();
  if (opts.min !== undefined) num = num.min(opts.min);
  if (opts.max !== undefined) num = num.max(opts.max);
  return z.union([z.literal("").transform(() => undefined), num]).optional();
}
