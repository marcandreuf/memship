"use client";

import { useTranslations } from "next-intl";
import { usePathname, Link } from "@/lib/i18n/routing";
import {
  LayoutDashboard,
  Users,
  UserCheck,
  CalendarDays,
  FolderOpen,
  Settings,
  UserCircle,
  ClipboardList,
  Receipt,
  FileText,
  Landmark,
  CalendarClock,
  Megaphone,
  IdCard,
  ScanLine,
  TrendingUp,
  MapPin,
  LogOut,
  ChevronsUpDown,
} from "lucide-react";
import type { User } from "@/features/auth/services/auth-api";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { usePermissions } from "@/features/auth/hooks/use-permissions";
import { useSettings } from "@/features/settings/hooks/use-settings";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
} from "@/components/ui/sidebar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

interface AppSidebarProps {
  user: User;
}

export function AppSidebar({ user }: AppSidebarProps) {
  const t = useTranslations();
  const pathname = usePathname();
  const { logout } = useAuth();
  const { data: settings } = useSettings();

  const logoUrl = settings?.logo_url
    ? `/api/uploads${settings.logo_url.replace("/uploads", "")}?t=${new Date(settings.updated_at).getTime()}`
    : null;

  const { isStaff: isAdmin, has, hasAny } = usePermissions();
  const commsEnabled = Boolean(settings?.features?.communications);
  const cardEnabled = Boolean(settings?.features?.member_card);
  const bookingsEnabled = Boolean(settings?.features?.bookings);

  // Nav is grouped (separated by dividers): home/news, then the staff groups
  // (people/club, money, comms), then the user's own items, then system.
  // Payment method has no nav entry — it lives as a tab on the profile page.
  //
  // Every item renders from the permission its destination is guarded by, so a
  // narrow custom role sees exactly what it can open. A feature flag and a
  // permission are ANDed: the flag says the club uses the feature at all.
  //
  // **Additive, not either/or.** `member` is pinned to every account, so staff
  // hold every `self.*` key too — an account that gains one administrative
  // permission must not lose its personal nav. The staff groups are appended
  // when the account is staff; the personal groups always render, gated on the
  // `self.*` keys. `/activities` and `/dashboard` appear on both sides and are
  // deduplicated below, first occurrence winning, so the staff catalog (which
  // shows drafts) beats the member catalog for anyone holding both.
  const seenHrefs = new Set<string>();
  const navGroups = [
    [
      { href: "/dashboard", label: t("nav.dashboard"), icon: LayoutDashboard, show: true },
      { href: "/announcements", label: t("nav.announcements"), icon: Megaphone, show: commsEnabled && has("self.communications.read") },
    ],
    ...(isAdmin
      ? [
          [
            { href: "/members", label: t("nav.members"), icon: Users, show: has("members.read") },
            { href: "/members/pending", label: t("nav.pendingRegistrations"), icon: UserCheck, show: has("members.approve") },
            { href: "/groups", label: t("nav.groups"), icon: FolderOpen, show: has("membership.read") },
            { href: "/activities", label: t("nav.activities"), icon: CalendarDays, show: has("activities.read") },
            { href: "/spaces", label: t("bookings.nav"), icon: MapPin, show: bookingsEnabled && has("bookings.read") },
            // Scanning renders the member's card, which is `members.read` data.
            { href: "/scan", label: t("nav.scan"), icon: ScanLine, show: cardEnabled && has("members.read") },
          ],
          [
            { href: "/receipts", label: t("nav.receipts"), icon: Receipt, show: has("billing.read") },
            { href: "/mandates", label: t("nav.mandates"), icon: FileText, show: has("billing.read") },
            { href: "/remittances", label: t("nav.remittances"), icon: Landmark, show: has("billing.read") },
            { href: "/billing-runs", label: t("nav.billingRuns"), icon: CalendarClock, show: has("billing.read") },
            { href: "/annual-summary", label: t("annualSummary.title"), icon: TrendingUp, show: has("reports.read") },
          ],
          [
            { href: "/communications", label: t("nav.communications"), icon: Megaphone, show: commsEnabled && has("communications.read") },
          ],
        ]
      : []),
    [
      { href: "/activities", label: t("nav.activities"), icon: CalendarDays, show: has("self.activities.read") },
      { href: "/book", label: t("bookings.navBook"), icon: MapPin, show: bookingsEnabled && has("self.bookings.write") },
    ],
    [
      { href: "/my-activities", label: t("activities.registration.myActivities"), icon: ClipboardList, show: has("self.registrations.read") },
      { href: "/my-bookings", label: t("bookings.navMyBookings"), icon: ClipboardList, show: bookingsEnabled && has("self.bookings.read") },
      { href: "/my-receipts", label: t("receipts.myReceipts"), icon: Receipt, show: has("self.billing.read") },
      { href: "/my-card", label: t("nav.myCard"), icon: IdCard, show: cardEnabled && has("self.card.read") },
    ],
    ...(isAdmin
      ? [
          [
            // Settings is a bag of tabs with their own gates — membership types
            // is reachable on `membership.write` alone, so this is an OR.
            {
              href: "/settings",
              label: t("nav.settings"),
              icon: Settings,
              show: hasAny(
                "settings.read",
                "membership.write",
                "roles.read",
                "users.read",
                "settings.custom_fields.write",
              ),
            },
          ],
        ]
      : []),
  ]
    .map((group) => group.filter((item) => item.show))
    .map((group) => {
      const kept = group.filter((item) => !seenHrefs.has(item.href));
      kept.forEach((item) => seenHrefs.add(item.href));
      return kept;
    })
    .filter((group) => group.length > 0);

  const initials = `${user.first_name?.[0] ?? ""}${user.last_name?.[0] ?? ""}`.toUpperCase();

  return (
    <Sidebar collapsible="icon" variant="sidebar">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link href="/dashboard">
                {logoUrl ? (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img
                    src={logoUrl}
                    alt={settings?.name || t("app.name")}
                    className="size-8 rounded-lg object-contain"
                  />
                ) : (
                  <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground text-sm font-bold">
                    M
                  </div>
                )}
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-semibold">{settings?.name || t("app.name")}</span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        {navGroups.map((group, gi) => (
          <SidebarGroup key={gi} className={gi > 0 ? "pt-0" : undefined}>
            {gi === 0 && <SidebarGroupLabel>{t("nav.menu")}</SidebarGroupLabel>}
            {gi > 0 && <SidebarSeparator className="mb-2" />}
            <SidebarGroupContent>
              <SidebarMenu>
                {group.map((item) => (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      asChild
                      isActive={pathname === item.href || pathname.startsWith(item.href + "/")}
                      tooltip={item.label}
                    >
                      <Link href={item.href}>
                        <item.icon />
                        <span>{item.label}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton
                  size="lg"
                  className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
                >
                  <Avatar className="h-8 w-8 rounded-lg">
                    {user.photo_url && (
                      /* Cache-buster per render — a re-upload keeps the same
                         filename (the member-photo-upload precedent). */
                      <AvatarImage
                        src={`/api/uploads${user.photo_url.replace("/uploads", "")}?t=${Date.now()}`}
                        alt=""
                        className="rounded-lg object-cover"
                      />
                    )}
                    <AvatarFallback className="rounded-lg text-xs">{initials}</AvatarFallback>
                  </Avatar>
                  <div className="grid flex-1 text-left text-sm leading-tight">
                    <span className="truncate font-semibold">
                      {user.first_name} {user.last_name}
                    </span>
                    <span className="truncate text-xs text-muted-foreground">
                      {user.email}
                    </span>
                  </div>
                  <ChevronsUpDown className="ml-auto size-4" />
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
                side="bottom"
                align="end"
                sideOffset={4}
              >
                <DropdownMenuItem asChild>
                  <Link href="/profile" className="cursor-pointer">
                    <UserCircle className="mr-2 h-4 w-4" />
                    {t("nav.profile")}
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => logout()} className="cursor-pointer">
                  <LogOut className="mr-2 h-4 w-4" />
                  {t("nav.logout")}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
