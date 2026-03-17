"use client";

import { useTranslations } from "next-intl";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/features/auth/hooks/use-auth";

export default function SettingsPage() {
  const t = useTranslations();
  const { user } = useAuth();

  if (user?.role !== "super_admin") {
    return (
      <div className="py-8 text-center text-muted-foreground">
        {t("settings.noAccess")}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">{t("nav.settings")}</h1>

      <Card>
        <CardHeader>
          <CardTitle>{t("settings.organization")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {t("settings.comingSoon")}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
