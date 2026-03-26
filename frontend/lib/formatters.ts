/**
 * Shared formatting utilities for currency and dates.
 * Uses org settings (currency, date_format, locale) for consistent display.
 *
 * Currency formatting uses Intl.NumberFormat with the org locale:
 *   es/ca → 1.234,56 € (European)
 *   en    → 1,234.56 € (Anglo)
 */

const LOCALE_MAP: Record<string, string> = {
  es: "es-ES",
  ca: "ca-ES",
  en: "en-GB",
};

export function formatCurrency(
  amount: number | string,
  currency: string = "EUR",
  locale: string = "es"
): string {
  const num = typeof amount === "string" ? parseFloat(amount) : amount;
  if (isNaN(num)) return "—";

  const intlLocale = LOCALE_MAP[locale] || LOCALE_MAP.es;
  return new Intl.NumberFormat(intlLocale, {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    useGrouping: true,
  }).format(num);
}

export function formatDate(
  dateStr: string | null | undefined,
  dateFormat: string = "DD/MM/YYYY"
): string {
  if (!dateStr) return "—";

  // Handle both ISO datetime and date-only strings
  const d = new Date(dateStr.includes("T") ? dateStr : `${dateStr}T00:00:00`);
  if (isNaN(d.getTime())) return dateStr;

  const day = String(d.getDate()).padStart(2, "0");
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const year = d.getFullYear();

  switch (dateFormat) {
    case "MM/DD/YYYY":
      return `${month}/${day}/${year}`;
    case "YYYY-MM-DD":
      return `${year}-${month}-${day}`;
    case "DD/MM/YYYY":
    default:
      return `${day}/${month}/${year}`;
  }
}

export function formatDateTime(
  dateStr: string | null | undefined,
  dateFormat: string = "DD/MM/YYYY"
): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;

  const datePart = formatDate(dateStr, dateFormat);
  const hours = String(d.getHours()).padStart(2, "0");
  const minutes = String(d.getMinutes()).padStart(2, "0");
  return `${datePart} ${hours}:${minutes}`;
}
