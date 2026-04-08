import { getRequestConfig } from "next-intl/server";
import { routing } from "./routing";

export default getRequestConfig(async ({ requestLocale }) => {
  let locale = await requestLocale;

  if (!locale || !routing.locales.includes(locale as typeof routing.locales[number])) {
    locale = routing.defaultLocale;
  }

  const common = (await import(`@/locales/${locale}/common.json`)).default;
  const auth = (await import(`@/locales/${locale}/auth.json`)).default;
  const members = (await import(`@/locales/${locale}/members.json`)).default;
  const dashboard = (await import(`@/locales/${locale}/dashboard.json`)).default;
  const settings = (await import(`@/locales/${locale}/settings.json`)).default;
  const activities = (await import(`@/locales/${locale}/activities.json`)).default;
  const receipts = (await import(`@/locales/${locale}/receipts.json`)).default;
  const mandates = (await import(`@/locales/${locale}/mandates.json`)).default;
  const remittances = (await import(`@/locales/${locale}/remittances.json`)).default;

  return {
    locale,
    messages: { ...common, ...auth, ...members, ...dashboard, ...settings, ...activities, ...receipts, ...mandates, ...remittances },
  };
});
