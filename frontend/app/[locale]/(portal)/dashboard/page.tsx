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
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { useMembers } from "@/features/members/hooks/use-members";
import { useActivities } from "@/features/activities/hooks/use-activities";
import { useGroups } from "@/features/groups/hooks/use-groups";
import { useMyRegistrations, useRegistrationStats } from "@/features/activities/hooks/use-registrations";
import { useActivity } from "@/features/activities/hooks/use-activities";
import type { RegistrationData } from "@/features/activities/services/registrations-api";

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

const REGISTRATION_COLORS: Record<string, string> = {
  confirmed: "hsl(142, 71%, 45%)",
  waitlist: "hsl(48, 96%, 53%)",
  cancelled: "hsl(0, 0%, 64%)",
  pending: "hsl(220, 9%, 64%)",
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
                tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{
                  fontSize: "0.75rem",
                  borderRadius: "0.375rem",
                  backgroundColor: "var(--popover)",
                  color: "var(--popover-foreground)",
                  border: "1px solid var(--border)",
                }}
                cursor={{ fill: "var(--accent)" }}
              />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={20}>
                {data.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
                <LabelList
                  dataKey="value"
                  position="right"
                  style={{ fontSize: 12, fontWeight: 600, fill: "var(--muted-foreground)" }}
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

const REG_STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  confirmed: "default",
  waitlist: "secondary",
  cancelled: "destructive",
  pending: "outline",
};

function UpcomingActivityCard({ registration }: { registration: RegistrationData }) {
  const t = useTranslations();
  const { data: activity } = useActivity(registration.activity_id);

  return (
    <Link
      href={`/activities/${registration.activity_id}`}
      className="block rounded-lg border p-3 hover:bg-accent transition-colors"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="font-medium text-sm truncate">
            {activity?.name || `Activity #${registration.activity_id}`}
          </p>
          {activity && (
            <p className="text-xs text-muted-foreground">
              {new Date(activity.starts_at).toLocaleDateString(undefined, {
                month: "short", day: "numeric", year: "numeric",
              })}
              {activity.location && ` · ${activity.location}`}
            </p>
          )}
        </div>
        <Badge variant={REG_STATUS_VARIANTS[registration.status] || "outline"} className="shrink-0">
          {t(`activities.registration.status.${registration.status}`)}
        </Badge>
      </div>
    </Link>
  );
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
  const { data: regStats } = useRegistrationStats();

  // Member: my registrations
  const { data: myRegistrations } = useMyRegistrations(
    !isAdmin ? { per_page: 5 } : {}
  );

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

  const registrationChartData = useMemo<ChartItem[]>(() => [
    { name: t("dashboard.confirmedRegistrations"), value: regStats?.confirmed ?? 0, color: REGISTRATION_COLORS.confirmed },
    { name: t("dashboard.waitlistRegistrations"), value: regStats?.waitlist ?? 0, color: REGISTRATION_COLORS.waitlist },
    { name: t("dashboard.pendingRegistrations"), value: regStats?.pending ?? 0, color: REGISTRATION_COLORS.pending },
    { name: t("dashboard.cancelledRegistrations"), value: regStats?.cancelled ?? 0, color: REGISTRATION_COLORS.cancelled },
  ], [regStats, t]);

  const activeRegistrations = myRegistrations?.items.filter(
    (r) => r.status === "confirmed" || r.status === "waitlist"
  ) || [];

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

          {/* Registrations chart + summary cards */}
          <div className="grid gap-4 sm:grid-cols-2">
            <StatusBarChart
              title={t("dashboard.totalRegistrations")}
              data={registrationChartData}
            />
            <div className="grid gap-3 grid-cols-1">
              <StatCard
                label={t("dashboard.totalGroups")}
                value={groups?.length ?? "—"}
                href="/groups"
              />
            </div>
          </div>
        </div>
      )}

      {!isAdmin && (
        <div className="space-y-4">
          <Card>
            <CardContent className="py-3 px-4">
              <p className="text-muted-foreground">
                {t("dashboard.memberWelcome")}
              </p>
              {user?.member_number && (
                <p className="mt-1 font-mono text-sm">
                  {t("dashboard.yourNumber")}: {user.member_number}
                </p>
              )}
            </CardContent>
          </Card>

          {/* Upcoming activities */}
          <Card>
            <CardHeader className="py-3 px-4">
              <CardTitle className="text-base">{t("dashboard.upcomingActivities")}</CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4 pt-0">
              {activeRegistrations.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("dashboard.noUpcoming")}</p>
              ) : (
                <div className="space-y-2">
                  {activeRegistrations.map((reg) => (
                    <UpcomingActivityCard key={reg.id} registration={reg} />
                  ))}
                  {myRegistrations && myRegistrations.meta.total > 5 && (
                    <Link
                      href="/my-activities"
                      className="block text-sm text-primary hover:underline pt-1"
                    >
                      {t("common.view")} {t("activities.registration.myActivities").toLowerCase()} →
                    </Link>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
