"use client";

import { SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { NotificationBell } from "@/components/layout/notification-bell";
import { useSettings } from "@/features/settings/hooks/use-settings";

export function Header() {
  const { data: settings } = useSettings();
  const commsEnabled = Boolean(settings?.features?.communications);

  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="mr-2 !h-4" />
      <div className="ml-auto flex items-center gap-1">
        {commsEnabled && <NotificationBell />}
        <ThemeToggle />
      </div>
    </header>
  );
}
