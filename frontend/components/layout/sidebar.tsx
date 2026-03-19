"use client";

import { useTranslations } from "next-intl";
import { usePathname, Link } from "@/lib/i18n/routing";
import type { User } from "@/features/auth/services/auth-api";

interface SidebarProps {
  user: User;
}

export function Sidebar({ user }: SidebarProps) {
  const t = useTranslations();
  const pathname = usePathname();

  const isAdmin = user.role === "admin" || user.role === "super_admin";

  const navItems = [
    { href: "/dashboard", label: t("nav.dashboard"), roles: ["super_admin", "admin", "member"] },
    { href: "/activities", label: t("nav.activities"), roles: ["super_admin", "admin", "member"] },
    ...(!isAdmin
      ? [{ href: "/my-activities", label: t("activities.registration.myActivities"), roles: ["member"] }]
      : []),
    ...(isAdmin
      ? [
          { href: "/members", label: t("nav.members"), roles: ["super_admin", "admin"] },
          { href: "/groups", label: t("nav.groups"), roles: ["super_admin", "admin"] },
        ]
      : []),
    { href: "/profile", label: t("nav.profile"), roles: ["super_admin", "admin", "member"] },
    ...(isAdmin
      ? [{ href: "/settings", label: t("nav.settings"), roles: ["super_admin", "admin"] }]
      : []),
  ];

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden md:flex md:w-64 md:flex-col md:border-r md:bg-card">
        <div className="flex h-14 items-center border-b px-4">
          <Link href="/dashboard" className="text-lg font-semibold">
            {t("app.name")}
          </Link>
        </div>
        <nav className="flex-1 space-y-1 p-3">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`block rounded-md px-3 py-2 text-sm transition-colors ${
                pathname === item.href || pathname.startsWith(item.href + "/")
                  ? "bg-primary text-primary-foreground"
                  : "hover:bg-accent"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>

      {/* Mobile bottom nav */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 flex border-t bg-card md:hidden">
        {navItems.slice(0, 4).map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`flex flex-1 flex-col items-center py-2 text-xs transition-colors ${
              pathname === item.href || pathname.startsWith(item.href + "/")
                ? "text-primary"
                : "text-muted-foreground"
            }`}
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </>
  );
}
