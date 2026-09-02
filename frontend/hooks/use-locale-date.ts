"use client";

import { useMemo } from "react";
import { useLocale } from "next-intl";
import { formatNamedDate } from "@/lib/formatters";

type DateInput = string | null | undefined;

/**
 * Month-name date formatters bound to the locale the user picked in the app.
 *
 * `toLocaleDateString(undefined, …)` resolves to the *browser* locale, so a
 * member reading the app in Catalan on an English browser gets English months.
 *
 * For the all-numeric form governed by the org's `date_format` setting, use
 * `useFormatters` instead.
 */
export function useLocaleDate() {
  const locale = useLocale();

  return useMemo(
    () => ({
      shortDate: (date: DateInput) => formatNamedDate(date, locale, "short"),
      shortDateTime: (date: DateInput) => formatNamedDate(date, locale, "short", true),
      longDate: (date: DateInput) => formatNamedDate(date, locale, "long"),
      longDateTime: (date: DateInput) => formatNamedDate(date, locale, "long", true),
    }),
    [locale]
  );
}
