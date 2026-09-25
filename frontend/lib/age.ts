/**
 * Mirrors backend `app/domains/persons/age.py`, so the UI hides or flags what
 * the API would refuse.
 */

/** Whole years completed today, or null when the birth date is unknown. */
export function ageOn(dateOfBirth: string | null | undefined, today = new Date()): number | null {
  const match = dateOfBirth?.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return null;
  const [year, month, day] = match.slice(1).map(Number);
  let age = today.getFullYear() - year;
  const beforeBirthday =
    today.getMonth() + 1 < month || (today.getMonth() + 1 === month && today.getDate() < day);
  if (beforeBirthday) age -= 1;
  return age;
}

export type AgeProblem = "birth_date_required" | "below_min_age" | "above_max_age";

/** Why this birth date does not satisfy an age range; null when it does. */
export function ageRestrictionProblem(
  dateOfBirth: string | null | undefined,
  minAge: number | null | undefined,
  maxAge: number | null | undefined,
): AgeProblem | null {
  if (minAge == null && maxAge == null) return null;
  const age = ageOn(dateOfBirth);
  if (age === null) return "birth_date_required";
  if (minAge != null && age < minAge) return "below_min_age";
  if (maxAge != null && age > maxAge) return "above_max_age";
  return null;
}
