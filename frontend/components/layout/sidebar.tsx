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

  const isAdmin = user.role === "admin" || user.role === "super_admin";
  const commsEnabled = Boolean(settings?.features?.communications);
  const cardEnabled = Boolean(settings?.features?.member_card);
  const bookingsEnabled = Boolean(settings?.features?.bookings);

  // Nav is grouped (separated by dividers): home/news, then club-wide items,
  // then the user's own items; admins get people/club, money, comms, system.
  // Payment method has no nav entry — it lives as a tab on the profile page.
  const navGroups = (
    isAdmin
      ? [
          [
            { href: "/dashboard", label: t("nav.dashboard"), icon: LayoutDashboard, show: true },
          ],
          [
            { href: "/members", label: t("nav.members"), icon: Users, show: true },
            { href: "/members/pending", label: t("nav.pendingRegistrations"), icon: UserCheck, show: true },
            { href: "/groups", label: t("nav.groups"), icon: FolderOpen, show: true },
            { href: "/activities", label: t("nav.activities"), icon: CalendarDays, show: true },
            { href: "/spaces", label: t("bookings.nav"), icon: MapPin, show: bookingsEnabled },
            { href: "/scan", label: t("nav.scan"), icon: ScanLine, show: cardEnabled },
          ],
          [
            { href: "/receipts", label: t("nav.receipts"), icon: Receipt, show: true },
            { href: "/mandates", label: t("nav.mandates"), icon: FileText, show: true },
            { href: "/remittances", label: t("nav.remittances"), icon: Landmark, show: true },
            { href: "/billing-runs", label: t("nav.billingRuns"), icon: CalendarClock, show: true },
            { href: "/annual-summary", label: t("annualSummary.title"), icon: TrendingUp, show: true },
          ],
          [
            { href: "/communications", label: t("nav.communications"), icon: Megaphone, show: commsEnabled },
          ],
          [
            { href: "/settings", label: t("nav.settings"), icon: Settings, show: true },
          ],
        ]
      : [
          [
            { href: "/dashboard", label: t("nav.dashboard"), icon: LayoutDashboard, show: true },
            { href: "/announcements", label: t("nav.announcements"), icon: Megaphone, show: commsEnabled },
          ],
          [
            { href: "/activities", label: t("nav.activities"), icon: CalendarDays, show: true },
            { href: "/book", label: t("bookings.navBook"), icon: MapPin, show: bookingsEnabled },
          ],
          [
            { href: "/my-activities", label: t("activities.registration.myActivities"), icon: ClipboardList, show: true },
            { href: "/my-bookings", label: t("bookings.navMyBookings"), icon: ClipboardList, show: bookingsEnabled },
            { href: "/my-receipts", label: t("receipts.myReceipts"), icon: Receipt, show: true },
            { href: "/my-card", label: t("nav.myCard"), icon: IdCard, show: cardEnabled },
          ],
        ]
  )
    .map((group) => group.filter((item) => item.show))
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
