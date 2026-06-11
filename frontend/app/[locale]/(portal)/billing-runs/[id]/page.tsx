"use client";

import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import {
  Card, CardContent, CardHeader, CardTitle,
} from "@/components/ui/card";
import { DetailHeader } from "@/components/entity/detail-header";
import { DetailSection } from "@/components/entity/detail-section";
import { DetailSkeleton } from "@/components/ui/skeletons";
import { useFormatters } from "@/hooks/use-formatters";
import { useBillingRun } from "@/features/settings/hooks/use-billing-runs";

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  success: "default",
  failed: "destructive",
  partial_failure: "secondary",
};

export default function BillingRunDetailPage() {
  const t = useTranslations();
  const { id } = useParams<{ id: string }>();
  const { data: run, isLoading } = useBillingRun(Number(id));
  const { formatDate, formatDateTime } = useFormatters();

  if (isLoading) return <DetailSkeleton />;
  if (!run) return <p className="text-center py-8">{t("billingRuns.notFound")}</p>;

  const fields = [
    { label: t("billingRuns.fields.id"), value: String(run.id) },
    { label: t("billingRuns.fields.frequency"), value: t(`billingRuns.frequencyValue.${run.frequency}`) },
    { label: t("billingRuns.fields.period"), value: `${formatDate(run.period_start)} — ${formatDate(run.period_end)}` },
    { label: t("billingRuns.fields.triggeredBy"), value: t(`billingRuns.triggeredByValue.${run.triggered_by}`) },
    { label: t("billingRuns.fields.receiptsGenerated"), value: String(run.receipts_generated) },
    { label: t("billingRuns.fields.startedAt"), value: formatDateTime(run.started_at) },
    { label: t("billingRuns.fields.finishedAt"), value: formatDateTime(run.finished_at) },
  ];

  return (
    <div className="space-y-4">
      <DetailHeader
        breadcrumbs={[
          { label: t("billingRuns.title"), href: "/billing-runs" },
          { label: `#${run.id}` },
        ]}
        title={`#${run.id}`}
        badge={{
          label: t(`billingRuns.statusValue.${run.status}`),
          variant: STATUS_VARIANTS[run.status] || "outline",
        }}
      />

      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-base">{t("billingRuns.detailTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4 pt-0">
          <DetailSection fields={fields} columns={2} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-base">{t("billingRuns.errorsTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4 pt-0">
          {run.errors.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("billingRuns.noErrors")}</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {run.errors.map((err, i) => (
                <li key={i} className="font-mono text-destructive">
                  {typeof err === "object" ? JSON.stringify(err) : String(err)}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
