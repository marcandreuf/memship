"use client";

import { useTranslations } from "next-intl";
import { ScanLine } from "lucide-react";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { usePermissions } from "@/features/auth/hooks/use-permissions";
import { ScanPanel } from "@/features/member-card/components/scan-panel";

export default function ScanPage() {
  const t = useTranslations();
  const { user } = useAuth();
  // Scanning renders the scanned member's record.
  const { has } = usePermissions();
  const isAdmin = has("members.read");

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
