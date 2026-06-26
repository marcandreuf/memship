"use client";

import { Bell } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/lib/i18n/routing";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  useMarkRead,
  useNotifications,
  useUnreadCount,
} from "@/features/communications/hooks/use-notifications";

export function NotificationBell() {
  const t = useTranslations();
  const router = useRouter();
  const { data: unread } = useUnreadCount();
  const { data: notifications } = useNotifications();
  const markRead = useMarkRead();

  const count = unread?.count ?? 0;
  const items = (notifications ?? []).slice(0, 8);

  function openItem(id: number, readAt: string | null) {
    if (!readAt) markRead.mutate({ ids: [id] });
    router.push("/announcements");
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="relative"
          aria-label={t("communications.notifications.title")}
        >
          <Bell className="size-5" />
          {count > 0 && (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-semibold text-primary-foreground">
              {count > 9 ? "9+" : count}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <div className="flex items-center justify-between px-2 py-1.5">
          <DropdownMenuLabel className="p-0">
            {t("communications.notifications.title")}
          </DropdownMenuLabel>
          {count > 0 && (
            <button
              className="text-xs text-primary hover:underline"
              onClick={(e) => {
                e.preventDefault();
                markRead.mutate({ all: true });
              }}
            >
              {t("communications.notifications.markAllRead")}
            </button>
          )}
        </div>
        <DropdownMenuSeparator />
        {items.length === 0 ? (
          <p className="px-2 py-6 text-center text-sm text-muted-foreground">
            {t("communications.notifications.empty")}
          </p>
        ) : (
          items.map((n) => (
            <DropdownMenuItem
              key={n.id}
              className="flex cursor-pointer flex-col items-start gap-0.5 py-2"
              onClick={() => openItem(n.id, n.read_at)}
            >
              <div className="flex w-full items-center gap-2">
                {!n.read_at && (
                  <span className="size-1.5 shrink-0 rounded-full bg-primary" />
                )}
                <span className={`truncate text-sm ${n.read_at ? "" : "font-semibold"}`}>
                  {n.title}
                </span>
              </div>
              {n.excerpt && (
                <span className="line-clamp-2 text-xs text-muted-foreground">
                  {n.excerpt}
                </span>
              )}
            </DropdownMenuItem>
          ))
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="cursor-pointer justify-center text-sm text-primary"
          onClick={() => router.push("/announcements")}
        >
          {t("communications.notifications.viewAll")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
