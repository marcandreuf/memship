"use client";

import { useTranslations } from "next-intl";
import { usePathname, Link } from "@/lib/i18n/routing";
import { locales, type Locale } from "@/lib/i18n/config";
import { Button } from "@/components/ui/button";
import type { User } from "@/features/auth/services/auth-api";
import { useAuth } from "@/features/auth/hooks/use-auth";

interface HeaderProps {
  user: User;
}

export function Header({ user }: HeaderProps) {
  const t = useTranslations();
  const pathname = usePathname();
  const { logout } = useAuth();

  return (
    <header className="flex h-14 items-center justify-between border-b bg-card px-4">
      {/* Mobile: app name */}
      <Link href="/dashboard" className="text-lg font-semibold md:hidden">
        {t("app.name")}
      </Link>

      <div className="hidden md:block" />

      <div className="flex items-center gap-3">
        {/* Locale switcher */}
        <div className="flex gap-1">
          {locales.map((locale) => (
            <Link
              key={locale}
              href={pathname}
              locale={locale as Locale}
              className="rounded px-2 py-1 text-xs hover:bg-accent transition-colors"
            >
              {locale.toUpperCase()}
            </Link>
          ))}
        </div>

        {/* User info */}
        <span className="hidden text-sm text-muted-foreground sm:block">
          {user.first_name} {user.last_name}
        </span>

        <Button variant="outline" size="sm" onClick={() => logout()}>
          {t("nav.logout")}
        </Button>
      </div>
    </header>
  );
}
