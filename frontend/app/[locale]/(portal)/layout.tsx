"use client";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { AppSidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { BrandTheme } from "@/components/layout/brand-theme";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { useRouter, usePathname } from "@/lib/i18n/routing";
import { useEffect } from "react";

const ADMIN_ROUTES = ["/members", "/groups", "/receipts", "/settings"];

export default function PortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoading, isAuthenticated } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  useEffect(() => {
    if (!isLoading && user) {
      const isAdmin = user.role === "admin" || user.role === "super_admin";
      if (!isAdmin && ADMIN_ROUTES.some((r) => pathname === r || pathname.startsWith(r + "/"))) {
        router.push("/dashboard");
      }
    }
  }, [isLoading, user, pathname, router]);

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

  return (
    <SidebarProvider>
      <BrandTheme />
      <AppSidebar user={user} />
      <SidebarInset>
        <Header />
        <main className="flex-1 p-4 md:p-6">{children}</main>
      </SidebarInset>
    </SidebarProvider>
  );
}
