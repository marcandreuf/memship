"use client";

import { useMemo, useState } from "react";
import { useTranslations, useLocale } from "next-intl";
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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TableSkeleton } from "@/components/ui/skeletons";
import { useAnnualSummary } from "@/features/reports/hooks/use-annual-summary";
import { useFormatters } from "@/hooks/use-formatters";

const REVENUE_COLOR = "hsl(142, 71%, 45%)";
const OUTSTANDING_COLOR = "hsl(48, 96%, 53%)";

const TOOLTIP_STYLE = {
  fontSize: "0.75rem",
  borderRadius: "0.375rem",
  backgroundColor: "var(--popover)",
  color: "var(--popover-foreground)",
  border: "1px solid var(--border)",
} as const;

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <Card className="py-3 gap-1">
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
}

export default function AnnualSummaryPage() {
  const t = useTranslations();
  const locale = useLocale();
  const { formatCurrency } = useFormatters();
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(currentYear);
  const { data, isLoading } = useAnnualSummary(year);

  const years = useMemo(
    () => Array.from({ length: 5 }, (_, i) => currentYear - i),
    [currentYear]
  );

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
      newMembers: data.new_members_by_month[i] ?? 0,
    }));
  }, [data, monthLabels]);

  const yearRevenue = data
    ? data.revenue_by_month.reduce((a, b) => a + b, 0)
    : 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("annualSummary.title")}</h1>
        <Select value={String(year)} onValueChange={(v) => setYear(Number(v))}>
          <SelectTrigger className="w-28">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {years.map((y) => (
              <SelectItem key={y} value={String(y)}>
                {y}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isLoading || !data ? (
        <TableSkeleton />
      ) : (
        <>
          <div className="grid gap-3 grid-cols-2 sm:grid-cols-4">
            <StatCard
              label={t("annualSummary.yearRevenue")}
              value={formatCurrency(yearRevenue)}
            />
            <StatCard label={t("annualSummary.newMembers")} value={data.new_members} />
            <StatCard
              label={t("annualSummary.activeMembers")}
              value={data.active_members}
            />
            <StatCard
              label={t("annualSummary.netGrowth")}
              value={`${data.net_growth >= 0 ? "+" : ""}${data.net_growth}`}
            />
          </div>

          <Card className="py-3">
            <CardHeader className="px-4">
              <CardTitle className="text-base">
                {t("annualSummary.revenueVsOutstanding")}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-2">
              <ResponsiveContainer width="100%" height={300}>
                <ComposedChart
                  data={chartData}
                  margin={{ top: 8, right: 16, bottom: 4, left: 0 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                    stroke="var(--border)"
                  />
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
                    name={t("annualSummary.revenue")}
                    fill={REVENUE_COLOR}
                    radius={[4, 4, 0, 0]}
                    barSize={16}
                  />
                  <Line
                    type="monotone"
                    dataKey="outstanding"
                    name={t("annualSummary.outstanding")}
                    stroke={OUTSTANDING_COLOR}
                    strokeWidth={2}
                    dot={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <div className="grid gap-3 md:grid-cols-2">
            <Card className="py-3">
              <CardHeader className="px-4">
                <CardTitle className="text-base">
                  {t("annualSummary.newMembersByMonth")}
                </CardTitle>
              </CardHeader>
              <CardContent className="px-2">
                <ResponsiveContainer width="100%" height={220}>
                  <ComposedChart
                    data={chartData}
                    margin={{ top: 8, right: 16, bottom: 4, left: 0 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      vertical={false}
                      stroke="var(--border)"
                    />
                    <XAxis
                      dataKey="month"
                      tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      allowDecimals={false}
                      tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
                      axisLine={false}
                      tickLine={false}
                      width={32}
                    />
                    <Tooltip contentStyle={TOOLTIP_STYLE} />
                    <Bar
                      dataKey="newMembers"
                      name={t("annualSummary.newMembers")}
                      fill={REVENUE_COLOR}
                      radius={[4, 4, 0, 0]}
                      barSize={16}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card className="py-3">
              <CardHeader className="px-4">
                <CardTitle className="text-base">
                  {t("annualSummary.topActivities")}
                </CardTitle>
              </CardHeader>
              <CardContent className="px-4">
                {data.activity_participation.length === 0 ? (
                  <p className="py-4 text-sm text-muted-foreground">
                    {t("common.noResults")}
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {data.activity_participation.map((p, i) => (
                      <li
                        key={i}
                        className="flex items-center justify-between text-sm"
                      >
                        <span className="truncate">{p.activity_name}</span>
                        <span className="ml-2 font-mono font-semibold">
                          {p.count}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
