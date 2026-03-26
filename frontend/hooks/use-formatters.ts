"use client";

import { useCallback } from "react";
import { useSettings } from "@/features/settings/hooks/use-settings";
import {
  formatCurrency as rawFormatCurrency,
  formatDate as rawFormatDate,
  formatDateTime as rawFormatDateTime,
} from "@/lib/formatters";

/**
 * Returns formatting functions bound to the org's currency, locale, and date format settings.
 *
 * Currency uses Intl.NumberFormat with org locale:
 *   es/ca → 1.234,56 €
 *   en    → €1,234.56
 */
export function useFormatters() {
  const { data: settings } = useSettings();
  const currency = settings?.currency || "EUR";
  const locale = settings?.locale || "es";
  const dateFormat = settings?.date_format || "DD/MM/YYYY";

  const fmtCurrency = useCallback(
    (amount: number | string) => rawFormatCurrency(amount, currency, locale),
    [currency, locale]
  );

  const fmtDate = useCallback(
    (dateStr: string | null | undefined) => rawFormatDate(dateStr, dateFormat),
    [dateFormat]
  );

  const fmtDateTime = useCallback(
    (dateStr: string | null | undefined) => rawFormatDateTime(dateStr, dateFormat),
    [dateFormat]
  );

  return { formatCurrency: fmtCurrency, formatDate: fmtDate, formatDateTime: fmtDateTime };
}
