"use client";

import { useMemo } from "react";
import { useTranslations, useLocale } from "next-intl";
import { Link } from "@/lib/i18n/routing";
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { CalendarClock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { useSettings } from "@/features/settings/hooks/use-settings";
import { useMembers } from "@/features/members/hooks/use-members";
import { useActivities } from "@/features/activities/hooks/use-activities";
import { useMyRegistrations, useRegistrationStats } from "@/features/activities/hooks/use-registrations";
import { useActivity } from "@/features/activities/hooks/use-activities";
import { useReceiptStats, useMyReceipts } from "@/features/receipts/hooks/use-receipts";
import { useAnnualSummary } from "@/features/reports/hooks/use-annual-summary";
import { ReminderList } from "@/features/reminders/components/reminder-list";
import { useFormatters } from "@/hooks/use-formatters";
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

const RECEIPT_COLORS: Record<string, string> = {
  paid: "hsl(142, 71%, 45%)",
  emitted: "hsl(210, 70%, 55%)",
  pending: "hsl(48, 96%, 53%)",
  overdue: "hsl(0, 84%, 60%)",
  returned: "hsl(340, 70%, 55%)",
  cancelled: "hsl(0, 0%, 64%)",
  new: "hsl(220, 9%, 78%)",
};

const REGISTRATION_COLORS: Record<string, string> = {
  confirmed: "hsl(142, 71%, 45%)",
  waitlist: "hsl(48, 96%, 53%)",
  cancelled: "hsl(0, 0%, 64%)",
  pending: "hsl(220, 9%, 64%)",
};

const REVENUE_COLOR = "hsl(142, 71%, 45%)";
const OUTSTANDING_COLOR = "hsl(48, 96%, 53%)";

const TOOLTIP_STYLE = {
  fontSize: "0.75rem",
  borderRadius: "0.375rem",
  backgroundColor: "var(--popover)",
  color: "var(--popover-foreground)",
  border: "1px solid var(--border)",
} as const;

interface CounterItem {
  label: string;
  value: number;
  color: string;
}

// Condensed status distribution for the dashboard rail: a colored dot + label +
// count per status, with the total in the header. Replaces the full-width bar
// charts now that finance leads the dashboard.
function CounterCard({
  title,
  items,
  href,
}: {
  title: string;
  items: CounterItem[];
  href?: string;
}) {
  const total = items.reduce((sum, i) => sum + i.value, 0);
  const content = (
    <Card className={`py-3 gap-2 ${href ? "hover:bg-accent/50 transition-colors" : ""}`}>
      <CardHeader className="px-4 flex flex-row items-baseline justify-between">
        <CardTitle className="text-sm">{title}</CardTitle>
        <span className="text-lg font-bold">{total}</span>
      </CardHeader>
      <CardContent className="px-4">
        <ul className="space-y-1">
          {items.map((i, idx) => (
            <li key={idx} className="flex items-center justify-between text-xs">
              <span className="flex items-center gap-2 min-w-0">
                <span
                  className="size-2 shrink-0 rounded-full"
                  style={{ backgroundColor: i.color }}
                />
                <span className="truncate text-muted-foreground">{i.label}</span>
              </span>
              <span className="font-mono font-medium">{i.value}</span>
            </li>
          ))}
        </ul>
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
    <Card className={`py-3 gap-1 ${href ? "hover:bg-accent/50 transition-colors" : ""}`}>
      <CardHeader className="px-4">
        <CardTitle className="text-xs font-medium text-muted-foreground">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4">
        <p className="text-2xl font-bold">{value}</p>
      </CardContent>
    </Card>
  );

  if (href) return <Link href={href}>{content}</Link>;
  return content;
}

// Current-year revenue (bars) with an outstanding/overdue overlay (line). Shares
// the annual-summary aggregate so both surfaces read the same numbers.
function FinanceGraphCard() {
  const t = useTranslations();
  const locale = useLocale();
  const { formatCurrency } = useFormatters();
  const currentYear = new Date().getFullYear();
  const { data } = useAnnualSummary(currentYear);

  const monthLabels = useMemo(
    () =>
      Array.from({ length: 12 }, (_, i) =>
        new Date(2000, i, 1).toLocaleString(locale, { month: "short" })
      ),
    [locale]
  );

  const chartData = useMemo(() => {
    if (!data) return [];
    return monthLabels.map((month, i) => ({
      month,
      revenue: data.revenue_by_month[i] ?? 0,
      outstanding: data.outstanding_by_month[i] ?? 0,
    }));
  }, [data, monthLabels]);

  return (
    <Card className="py-3">
      <CardHeader className="px-4 flex flex-row items-baseline justify-between">
        <CardTitle className="text-base">
          {t("dashboard.financeOverview", { year: currentYear })}
        </CardTitle>
        <Link
          href="/annual-summary"
          className="text-xs text-primary hover:underline"
        >
          {t("dashboard.viewAnnualSummary")} →
        </Link>
      </CardHeader>
      <CardContent className="px-2">
        <ResponsiveContainer width="100%" height={320}>
          <ComposedChart data={chartData} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
            <XAxis
              dataKey="month"
              tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
              axisLine={false}
              tickLine={false}
              width={56}
            />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              formatter={(value) => formatCurrency(Number(value))}
            />
            <Legend wrapperStyle={{ fontSize: "0.75rem" }} />
            <Bar
              dataKey="revenue"
              name={t("dashboard.revenue")}
              fill={REVENUE_COLOR}
              radius={[4, 4, 0, 0]}
              barSize={16}
            />
            <Line
              type="monotone"
              dataKey="outstanding"
              name={t("dashboard.outstanding")}
              stroke={OUTSTANDING_COLOR}
              strokeWidth={2}
              dot={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
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

// Admin rail card: the next few published activities by start date. Filters and
// sorts client-side (the activities list has no upcoming/date param yet).
function UpcomingActivitiesCard() {
  const t = useTranslations();
  const { formatDate } = useFormatters();
  const { data } = useActivities({ status: "published", per_page: 50 });

  const upcoming = useMemo(() => {
    const now = Date.now();
    return (data?.items ?? [])
      .filter((a) => new Date(a.starts_at).getTime() >= now)
      .sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime())
      .slice(0, 3);
  }, [data]);

  return (
    <Card className="py-3 gap-2">
      <CardHeader className="px-4">
        <CardTitle className="text-base">{t("dashboard.upcomingEvents")}</CardTitle>
      </CardHeader>
      <CardContent className="px-4">
        {upcoming.length === 0 ? (
          <p className="py-1 text-sm text-muted-foreground">{t("dashboard.noUpcoming")}</p>
        ) : (
          <div className="space-y-2">
            {upcoming.map((a) => (
              <Link
                key={a.id}
                href={`/activities/${a.id}`}
                className="block rounded-lg border p-2 hover:bg-accent transition-colors"
              >
                <p className="font-medium text-sm truncate">{a.name}</p>
                <p className="text-xs text-muted-foreground">
                  {formatDate(a.starts_at)}
                  {a.location && ` · ${a.location}`}
                </p>
              </Link>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function NextBillingRunCard() {
  const t = useTranslations();
  const { data: settings } = useSettings();
  const features = settings?.features ?? {};
  const enabled = Boolean(features.recurring_billing_enabled);
  const billingDay = Number(features.recurring_billing_day) || 1;

  let detail: string;
  if (!enabled) {
    detail = t("dashboard.recurringBillingDisabled");
  } else {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    let next = new Date(today.getFullYear(), today.getMonth(), billingDay);
    if (next < today) {
      next = new Date(today.getFullYear(), today.getMonth() + 1, billingDay);
    }
    const days = Math.round((next.getTime() - today.getTime()) / 86_400_000);
    detail = t("dashboard.nextBillingRunDetail", { day: billingDay, days });
  }

  return (
    <Link href="/billing-runs" className="block">
      <Card className="py-0 hover:bg-accent/50 transition-colors">
        <CardContent className="flex items-center gap-3 py-3 px-4">
          <CalendarClock className="size-5 shrink-0 text-muted-foreground" />
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">{t("dashboard.nextBillingRun")}</p>
            <p className="text-sm font-semibold">{detail}</p>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

export default function DashboardPage() {
  const t = useTranslations();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin" || user?.role === "super_admin";
  const { formatCurrency, formatDate } = useFormatters();

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

  const { data: regStats } = useRegistrationStats();
  const { data: receiptStats } = useReceiptStats();

  // Member: my registrations + receipts
  const { data: myRegistrations } = useMyRegistrations(
    !isAdmin ? { per_page: 5 } : {}
  );
  const myReceiptsParams = useMemo(() => {
    const p = new URLSearchParams();
    p.set("per_page", "5");
    return p;
  }, []);
  const { data: myReceipts } = useMyReceipts(!isAdmin ? myReceiptsParams : undefined);

  const memberCounters = useMemo<CounterItem[]>(() => [
    { label: t("status.active"), value: activeMembers?.meta.total ?? 0, color: MEMBER_COLORS.active },
    { label: t("status.pending"), value: pendingMembers?.meta.total ?? 0, color: MEMBER_COLORS.pending },
    { label: t("status.suspended"), value: suspendedMembers?.meta.total ?? 0, color: MEMBER_COLORS.suspended },
    { label: t("status.cancelled"), value: cancelledMembers?.meta.total ?? 0, color: MEMBER_COLORS.cancelled },
    { label: t("status.expired"), value: expiredMembers?.meta.total ?? 0, color: MEMBER_COLORS.expired },
  ], [activeMembers, pendingMembers, suspendedMembers, cancelledMembers, expiredMembers, t]);

  const activityCounters = useMemo<CounterItem[]>(() => [
    { label: t("activities.status.draft"), value: draftActivities?.meta.total ?? 0, color: ACTIVITY_COLORS.draft },
    { label: t("activities.status.published"), value: publishedActivities?.meta.total ?? 0, color: ACTIVITY_COLORS.published },
    { label: t("activities.status.archived"), value: archivedActivities?.meta.total ?? 0, color: ACTIVITY_COLORS.archived },
    { label: t("activities.status.cancelled"), value: cancelledActivities?.meta.total ?? 0, color: ACTIVITY_COLORS.cancelled },
  ], [draftActivities, publishedActivities, archivedActivities, cancelledActivities, t]);

  const registrationCounters = useMemo<CounterItem[]>(() => [
    { label: t("dashboard.confirmedRegistrations"), value: regStats?.confirmed ?? 0, color: REGISTRATION_COLORS.confirmed },
    { label: t("dashboard.waitlistRegistrations"), value: regStats?.waitlist ?? 0, color: REGISTRATION_COLORS.waitlist },
    { label: t("dashboard.pendingRegistrations"), value: regStats?.pending ?? 0, color: REGISTRATION_COLORS.pending },
    { label: t("dashboard.cancelledRegistrations"), value: regStats?.cancelled ?? 0, color: REGISTRATION_COLORS.cancelled },
  ], [regStats, t]);

  const receiptCounters = useMemo<CounterItem[]>(() => [
    { label: t("receipts.statusPaid"), value: receiptStats?.paid ?? 0, color: RECEIPT_COLORS.paid },
    { label: t("receipts.statusEmitted"), value: receiptStats?.emitted ?? 0, color: RECEIPT_COLORS.emitted },
    { label: t("receipts.statusPending"), value: (receiptStats?.pending ?? 0) + (receiptStats?.new ?? 0), color: RECEIPT_COLORS.pending },
    { label: t("receipts.statusOverdue"), value: receiptStats?.overdue ?? 0, color: RECEIPT_COLORS.overdue },
    { label: t("receipts.statusReturned"), value: receiptStats?.returned ?? 0, color: RECEIPT_COLORS.returned },
  ], [receiptStats, t]);

  const activeRegistrations = myRegistrations?.items.filter(
    (r) => r.status === "confirmed" || r.status === "waitlist"
  ) || [];

  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-bold">
        {t("dashboard.welcome", { name: user?.first_name ?? "", gender: user?.gender ?? "other" })}
      </h1>

      {isAdmin && (
        <div className="grid gap-3 lg:grid-cols-3">
          {/* Main (2/3): finance leads. */}
          <div className="lg:col-span-2 space-y-3">
            <FinanceGraphCard />

            <div className="grid gap-3 grid-cols-2 sm:grid-cols-3">
              <StatCard
                label={t("dashboard.pendingAmount")}
                value={formatCurrency(receiptStats?.pending_amount ?? 0)}
                href="/receipts?status=emitted"
              />
              <StatCard
                label={t("dashboard.paidThisMonth")}
                value={formatCurrency(receiptStats?.paid_this_month ?? 0)}
                href="/receipts?status=paid"
              />
              <StatCard
                label={t("dashboard.overdueAmount")}
                value={formatCurrency(receiptStats?.overdue_amount ?? 0)}
                href="/receipts?status=overdue"
              />
            </div>
          </div>

          {/* Rail (1/3): actionable today/this-week widgets. */}
          <div className="space-y-3">
            <ReminderList />
            <NextBillingRunCard />
            <UpcomingActivitiesCard />
            <CounterCard title={t("nav.members")} items={memberCounters} href="/members" />
            <CounterCard title={t("receipts.title")} items={receiptCounters} href="/receipts" />
            <CounterCard title={t("nav.activities")} items={activityCounters} href="/activities" />
            <CounterCard title={t("dashboard.totalRegistrations")} items={registrationCounters} />
          </div>
        </div>
      )}

      {!isAdmin && (
        <div className="space-y-4">
          <Card>
            <CardContent className="py-3 px-4">
              <p className="text-muted-foreground">
                {t("dashboard.memberWelcome", { gender: user?.gender ?? "other" })}
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

          {/* My recent receipts */}
          <Card>
            <CardHeader className="py-3 px-4">
              <CardTitle className="text-base">{t("receipts.myReceipts")}</CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4 pt-0">
              {!myReceipts?.items.length ? (
                <p className="text-sm text-muted-foreground">{t("receipts.noReceipts")}</p>
              ) : (
                <div className="space-y-2">
                  {myReceipts.items.map((r) => (
                    <div key={r.id} className="flex items-center justify-between rounded-lg border p-3">
                      <div className="min-w-0">
                        <p className="font-medium text-sm truncate">{r.description}</p>
                        <p className="text-xs text-muted-foreground">{formatDate(r.emission_date)}</p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="font-mono text-sm font-medium">{formatCurrency(r.total_amount)}</span>
                        <Badge variant={
                          r.status === "paid" ? "default" :
                          r.status === "overdue" || r.status === "returned" ? "destructive" : "secondary"
                        }>
                          {t(`receipts.status${r.status.charAt(0).toUpperCase() + r.status.slice(1)}`)}
                        </Badge>
                      </div>
                    </div>
                  ))}
                  {myReceipts.meta.total > 5 && (
                    <Link href="/my-receipts" className="block text-sm text-primary hover:underline pt-1">
                      {t("common.view")} {t("receipts.myReceipts").toLowerCase()} →
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
