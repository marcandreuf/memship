"use client";

import { useTranslations } from "next-intl";
import { usePathname, Link } from "@/lib/i18n/routing";
import {
  LayoutDashboard,
  Users,
  CalendarDays,
  FolderOpen,
  Settings,
  UserCircle,
  ClipboardList,
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
} from "@/components/ui/sidebar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

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

  const navItems = [
    { href: "/dashboard", label: t("nav.dashboard"), icon: LayoutDashboard, show: true },
    { href: "/activities", label: t("nav.activities"), icon: CalendarDays, show: true },
    { href: "/my-activities", label: t("activities.registration.myActivities"), icon: ClipboardList, show: !isAdmin },
    { href: "/members", label: t("nav.members"), icon: Users, show: isAdmin },
    { href: "/groups", label: t("nav.groups"), icon: FolderOpen, show: isAdmin },
    { href: "/settings", label: t("nav.settings"), icon: Settings, show: isAdmin },
  ].filter((item) => item.show);

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
        <SidebarGroup>
          <SidebarGroupLabel>{t("nav.menu")}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
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
