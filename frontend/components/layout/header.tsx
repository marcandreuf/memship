"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/lib/i18n/routing";
import { Button } from "@/components/ui/button";
import type { User } from "@/features/auth/services/auth-api";
import { useAuth } from "@/features/auth/hooks/use-auth";

interface HeaderProps {
  user: User;
}

export function Header({ user }: HeaderProps) {
  const t = useTranslations();
  const { logout } = useAuth();

  return (
    <header className="flex h-14 items-center justify-between border-b bg-card px-4">
      {/* Mobile: app name */}
      <Link href="/dashboard" className="text-lg font-semibold md:hidden">
        {t("app.name")}
      </Link>

      <div className="hidden md:block" />

      <div className="flex items-center gap-3">
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
