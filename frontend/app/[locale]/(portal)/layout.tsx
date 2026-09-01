"use client";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { usePermissions } from "@/features/auth/hooks/use-permissions";
import { PendingApproval } from "@/features/auth/components/pending-approval";
import { AppSidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { AppFooter } from "@/components/layout/footer";
import { BrandTheme } from "@/components/layout/brand-theme";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { useSettings } from "@/features/settings/hooks/use-settings";
import { useRouter, usePathname } from "@/lib/i18n/routing";
import { useEffect } from "react";

import { requiredFeature, requiredPermissions } from "@/lib/route-permissions";

export default function PortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoading, isAuthenticated } = useAuth();
  const { isStaff: isAdmin, hasAny } = usePermissions();
  const { data: settings } = useSettings();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  // Per-route, per-permission — the ordinal "admin routes" list this replaced
  // could only ask "are you staff", which sent a treasurer to /receipts and a
  // front-desk role to /members alike. The server still guards every endpoint;
  // this only decides where an unauthorized URL lands.
  useEffect(() => {
    if (!isLoading && user) {
      const required = requiredPermissions(pathname);
      if (required && !hasAny(...required)) {
        router.push("/dashboard");
      }
    }
  }, [isLoading, user, hasAny, pathname, router]);

  // A switched-off feature 404s its endpoints, so land on the dashboard rather
  // than on a shell whose every request fails. Waits for settings: acting on
  // the undefined first render would bounce anyone who deep-links here.
  useEffect(() => {
    if (!isLoading && user && settings) {
      const feature = requiredFeature(pathname);
      if (feature && !settings.features?.[feature]) {
        router.push("/dashboard");
      }
    }
  }, [isLoading, user, settings, pathname, router]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="animate-pulse text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  // Registration still awaiting admin approval: the backend closes every
  // feature route for this member, so show why instead of an empty portal.
  if (!isAdmin && user.member_status === "pending") {
    return (
      <>
        <BrandTheme />
        <PendingApproval user={user} />
      </>
    );
  }

  return (
    <SidebarProvider>
      <BrandTheme />
      <AppSidebar user={user} />
      <SidebarInset>
        <Header />
        {/* A div, not a main: SidebarInset is already the <main> landmark, and
            HTML forbids nesting one inside another. Two of them also made every
            `cy.get("main")` in the suite ambiguous. */}
        <div className="flex-1 p-4 md:p-6">{children}</div>
        <AppFooter />
      </SidebarInset>
    </SidebarProvider>
  );
}
