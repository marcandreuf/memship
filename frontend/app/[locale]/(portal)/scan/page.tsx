"use client";

import { useTranslations } from "next-intl";
import { ScanLine } from "lucide-react";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { ScanPanel } from "@/features/member-card/components/scan-panel";

export default function ScanPage() {
  const t = useTranslations();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin" || user?.role === "super_admin";

  if (!isAdmin) {
    return (
      <div className="py-8 text-center text-muted-foreground">
        {t("scan.noAccess")}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="flex items-center gap-2 text-2xl font-bold">
        <ScanLine className="h-6 w-6" />
        {t("scan.title")}
      </h1>
      <p className="text-sm text-muted-foreground">{t("scan.hint")}</p>
      <ScanPanel />
    </div>
  );
}
