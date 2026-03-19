"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/lib/i18n/routing";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Cell,
  ResponsiveContainer,
  Tooltip,
  LabelList,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { useMembers } from "@/features/members/hooks/use-members";
import { useActivities } from "@/features/activities/hooks/use-activities";
import { useGroups } from "@/features/groups/hooks/use-groups";

const MEMBER_COLORS: Record<string, string> = {
  active: "hsl(142, 71%, 45%)",
  pending: "hsl(48, 96%, 53%)",
  suspended: "hsl(0, 84%, 60%)",
  cancelled: "hsl(0, 0%, 64%)",
  expired: "hsl(220, 9%, 46%)",
};

const ACTIVITY_COLORS: Record<string, string> = {
  draft: "hsl(220, 9%, 64%)",
  published: "hsl(142, 71%, 45%)",
  archived: "hsl(48, 96%, 53%)",
  cancelled: "hsl(0, 84%, 60%)",
};

interface ChartItem {
  name: string;
  value: number;
  color: string;
}

function StatusBarChart({
  data,
  title,
  href,
}: {
  data: ChartItem[];
  title: string;
  href?: string;
}) {
  const hasData = data.some((d) => d.value > 0);
  const total = data.reduce((sum, d) => sum + d.value, 0);

  const content = (
    <Card className={href ? "hover:bg-accent/50 transition-colors" : ""}>
      <CardHeader className="pb-1 pt-3 px-4 flex flex-row items-baseline justify-between">
        <CardTitle className="text-base">{title}</CardTitle>
        <span className="text-xl font-bold">{total}</span>
      </CardHeader>
      <CardContent className="px-2 pb-3">
        {!hasData ? (
          <div className="flex items-center justify-center h-24 text-sm text-muted-foreground">
            —
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={5 * 32 + 8}>
            <BarChart
              data={data}
              layout="vertical"
              margin={{ top: 4, right: 40, bottom: 4, left: 0 }}
            >
              <XAxis type="number" hide />
              <YAxis
                type="category"
                dataKey="name"
                width={100}
                tick={{ fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{ fontSize: "0.75rem", borderRadius: "0.375rem" }}
                cursor={{ fill: "hsl(0, 0%, 95%)" }}
              />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={20}>
                {data.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
                <LabelList
                  dataKey="value"
                  position="right"
                  style={{ fontSize: 12, fontWeight: 600, fill: "hsl(0, 0%, 40%)" }}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );

  if (href) return <Link href={href}>{content}</Link>;
  return content;
}

function StatCard({
  label,
  value,
  href,
}: {
  label: string;
  value: number | string;
  href?: string;
}) {
  const content = (
    <Card className={href ? "hover:bg-accent/50 transition-colors" : ""}>
      <CardHeader className="pb-1 pt-3 px-4">
        <CardTitle className="text-xs font-medium text-muted-foreground">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-3">
        <p className="text-2xl font-bold">{value}</p>
      </CardContent>
    </Card>
  );

  if (href) return <Link href={href}>{content}</Link>;
  return content;
}

export default function DashboardPage() {
  const t = useTranslations();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin" || user?.role === "super_admin";

  // Member counts by status
  const { data: activeMembers } = useMembers(isAdmin ? { status: "active", per_page: 1 } : {});
  const { data: pendingMembers } = useMembers(isAdmin ? { status: "pending", per_page: 1 } : {});
  const { data: suspendedMembers } = useMembers(isAdmin ? { status: "suspended", per_page: 1 } : {});
  const { data: cancelledMembers } = useMembers(isAdmin ? { status: "cancelled", per_page: 1 } : {});
  const { data: expiredMembers } = useMembers(isAdmin ? { status: "expired", per_page: 1 } : {});

  // Activity counts by status
  const { data: draftActivities } = useActivities(isAdmin ? { status: "draft", per_page: 1 } : {});
  const { data: publishedActivities } = useActivities(isAdmin ? { status: "published", per_page: 1 } : {});
  const { data: archivedActivities } = useActivities(isAdmin ? { status: "archived", per_page: 1 } : {});
  const { data: cancelledActivities } = useActivities(isAdmin ? { status: "cancelled", per_page: 1 } : {});

  const { data: groups } = useGroups();

  const memberChartData = useMemo<ChartItem[]>(() => [
    { name: t("status.active"), value: activeMembers?.meta.total ?? 0, color: MEMBER_COLORS.active },
    { name: t("status.pending"), value: pendingMembers?.meta.total ?? 0, color: MEMBER_COLORS.pending },
    { name: t("status.suspended"), value: suspendedMembers?.meta.total ?? 0, color: MEMBER_COLORS.suspended },
    { name: t("status.cancelled"), value: cancelledMembers?.meta.total ?? 0, color: MEMBER_COLORS.cancelled },
    { name: t("status.expired"), value: expiredMembers?.meta.total ?? 0, color: MEMBER_COLORS.expired },
  ], [activeMembers, pendingMembers, suspendedMembers, cancelledMembers, expiredMembers, t]);

  const activityChartData = useMemo<ChartItem[]>(() => [
    { name: t("activities.status.draft"), value: draftActivities?.meta.total ?? 0, color: ACTIVITY_COLORS.draft },
    { name: t("activities.status.published"), value: publishedActivities?.meta.total ?? 0, color: ACTIVITY_COLORS.published },
    { name: t("activities.status.archived"), value: archivedActivities?.meta.total ?? 0, color: ACTIVITY_COLORS.archived },
    { name: t("activities.status.cancelled"), value: cancelledActivities?.meta.total ?? 0, color: ACTIVITY_COLORS.cancelled },
  ], [draftActivities, publishedActivities, archivedActivities, cancelledActivities, t]);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">
        {t("dashboard.welcome", { name: user?.first_name ?? "" })}
      </h1>

      {isAdmin && (
        <div className="space-y-4">
          {/* Bar charts side by side */}
          <div className="grid gap-4 sm:grid-cols-2">
            <StatusBarChart
              title={t("nav.members")}
              data={memberChartData}
              href="/members"
            />
            <StatusBarChart
              title={t("nav.activities")}
              data={activityChartData}
              href="/activities"
            />
          </div>

          {/* Groups card */}
          <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
            <StatCard
              label={t("dashboard.totalGroups")}
              value={groups?.length ?? "—"}
              href="/groups"
            />
          </div>
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
