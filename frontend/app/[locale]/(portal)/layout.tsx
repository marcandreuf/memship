"use client";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { useRouter } from "@/lib/i18n/routing";
import { useEffect } from "react";

export default function PortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoading, isAuthenticated } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isLoading, isAuthenticated, router]);

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
    <div className="flex min-h-screen">
      <Sidebar user={user} />
      <div className="flex flex-1 flex-col">
        <Header user={user} />
        <main className="flex-1 p-4 pb-20 md:p-6 md:pb-6">{children}</main>
      </div>
    </div>
  );
}
