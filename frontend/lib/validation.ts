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
