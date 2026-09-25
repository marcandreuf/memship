/** Lower-case and strip diacritics, so "padel" finds "pádel". */
function fold(text: string): string {
  return text.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
}

/**
 * Client-side counterpart of the backend's `match_words`: every word of
 * `query` must appear in one of `fields`, in any order, ignoring case and
 * accents. For lists whose endpoint returns every row and is filtered here.
 */
export function matchesSearch(query: string, ...fields: (string | null | undefined)[]): boolean {
  const words = fold(query).split(/\s+/).filter(Boolean);
  if (!words.length) return true;
  const haystacks = fields.filter((f): f is string => Boolean(f)).map(fold);
  return words.every((word) => haystacks.some((h) => h.includes(word)));
}
