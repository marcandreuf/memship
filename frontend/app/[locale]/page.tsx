"use client";

import { useTranslations } from "next-intl";
import { Link, usePathname } from "@/lib/i18n/routing";
import { locales, type Locale } from "@/lib/i18n/config";

export default function HomePage() {
  const t = useTranslations();
  const pathname = usePathname();

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 p-8">
      <div className="text-center">
        <h1 className="text-4xl font-bold">{t("home.welcome")}</h1>
        <p className="mt-2 text-lg text-muted-foreground">
          {t("home.description")}
        </p>
      </div>

      <div className="flex gap-3">
        {locales.map((locale) => (
          <Link
            key={locale}
            href={pathname}
            locale={locale as Locale}
            className="rounded-md border px-4 py-2 text-sm hover:bg-accent transition-colors"
          >
            {t(`locale.${locale}`)}
          </Link>
        ))}
      </div>

      <div className="flex gap-4">
        <Link
          href="/login"
          className="rounded-md bg-primary px-6 py-2 text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          {t("nav.login")}
        </Link>
        <Link
          href="/register"
          className="rounded-md border px-6 py-2 hover:bg-accent transition-colors"
        >
          {t("nav.register")}
        </Link>
      </div>
    </div>
  );
}
