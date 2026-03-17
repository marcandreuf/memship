"use client";

import { useTranslations } from "next-intl";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { useMembers } from "@/features/members/hooks/use-members";

export default function DashboardPage() {
  const t = useTranslations();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin" || user?.role === "super_admin";

  const { data: activeMembers } = useMembers(
    isAdmin ? { status: "active", per_page: 1 } : {}
  );
  const { data: pendingMembers } = useMembers(
    isAdmin ? { status: "pending", per_page: 1 } : {}
  );

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">
        {t("dashboard.welcome", { name: user?.first_name ?? "" })}
      </h1>

      {isAdmin && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {t("dashboard.activeMembers")}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">
                {activeMembers?.meta.total ?? "—"}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {t("dashboard.pendingMembers")}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">
                {pendingMembers?.meta.total ?? "—"}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {!isAdmin && (
        <Card>
          <CardContent className="pt-6">
            <p className="text-muted-foreground">
              {t("dashboard.memberWelcome")}
            </p>
            {user?.member_number && (
              <p className="mt-2 font-mono text-sm">
                {t("dashboard.yourNumber")}: {user.member_number}
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
