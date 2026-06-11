"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Pagination } from "@/components/entity/pagination";
import { TableSkeleton } from "@/components/ui/skeletons";
import { toast } from "sonner";
import { useBillingRuns, useRunBillingNow } from "@/features/settings/hooks/use-billing-runs";
import type { BillingRun, BillingFrequency } from "@/features/settings/services/billing-runs-api";
import { useFormatters } from "@/hooks/use-formatters";

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  success: "default",
  failed: "destructive",
  partial_failure: "secondary",
};

function StatusBadge({ status, t }: { status: string; t: (key: string) => string }) {
  return (
    <Badge variant={STATUS_VARIANTS[status] || "outline"}>
      {t(`billingRuns.statusValue.${status}`)}
    </Badge>
  );
}

export default function BillingRunsPage() {
  const t = useTranslations();
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [frequency, setFrequency] = useState("");
  const [status, setStatus] = useState("");

  const { data, isLoading } = useBillingRuns({
    page,
    per_page: 20,
    frequency: frequency || undefined,
    status: status || undefined,
  });
  const { formatDate } = useFormatters();

  const items = data?.items || [];
  const meta = data?.meta || { page: 1, per_page: 20, total: 0, total_pages: 1 };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t("billingRuns.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("billingRuns.subtitle")}</p>
        </div>
        <RunNowButton t={t} />
      </div>

      <div className="flex items-center gap-3">
        <Select value={frequency || "all"} onValueChange={(v) => { setFrequency(v === "all" ? "" : v); setPage(1); }}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder={t("billingRuns.columns.frequency")} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("billingRuns.frequencyValue.all")}</SelectItem>
            <SelectItem value="monthly">{t("billingRuns.frequencyValue.monthly")}</SelectItem>
            <SelectItem value="quarterly">{t("billingRuns.frequencyValue.quarterly")}</SelectItem>
            <SelectItem value="annual">{t("billingRuns.frequencyValue.annual")}</SelectItem>
          </SelectContent>
        </Select>
        <Select value={status || "all"} onValueChange={(v) => { setStatus(v === "all" ? "" : v); setPage(1); }}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder={t("billingRuns.columns.status")} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("billingRuns.statusValue.all")}</SelectItem>
            <SelectItem value="success">{t("billingRuns.statusValue.success")}</SelectItem>
            <SelectItem value="failed">{t("billingRuns.statusValue.failed")}</SelectItem>
            <SelectItem value="partial_failure">{t("billingRuns.statusValue.partial_failure")}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <TableSkeleton />
      ) : items.length === 0 ? (
        <p className="text-sm text-muted-foreground py-8 text-center">{t("billingRuns.empty")}</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("billingRuns.columns.date")}</TableHead>
              <TableHead>{t("billingRuns.columns.frequency")}</TableHead>
              <TableHead>{t("billingRuns.columns.period")}</TableHead>
              <TableHead>{t("billingRuns.columns.triggeredBy")}</TableHead>
              <TableHead>{t("billingRuns.columns.status")}</TableHead>
              <TableHead className="text-right">{t("billingRuns.columns.receipts")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((run: BillingRun) => (
              <TableRow
                key={run.id}
                className="cursor-pointer hover:bg-muted/50"
                onClick={() => router.push(`/billing-runs/${run.id}`)}
              >
                <TableCell className="text-sm">{formatDate(run.started_at)}</TableCell>
                <TableCell>{t(`billingRuns.frequencyValue.${run.frequency}`)}</TableCell>
                <TableCell className="text-sm">{formatDate(run.period_start)} — {formatDate(run.period_end)}</TableCell>
                <TableCell>{t(`billingRuns.triggeredByValue.${run.triggered_by}`)}</TableCell>
                <TableCell><StatusBadge status={run.status} t={t} /></TableCell>
                <TableCell className="text-right font-mono">{run.receipts_generated}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Pagination
        page={meta.page}
        totalPages={meta.total_pages}
        total={meta.total}
        perPage={meta.per_page}
        onPageChange={(p) => setPage(p)}
      />
    </div>
  );
}

function RunNowButton({ t }: { t: ReturnType<typeof useTranslations> }) {
  const [open, setOpen] = useState(false);
  const [frequency, setFrequency] = useState("all");
  const mutation = useRunBillingNow();

  async function handleRun() {
    try {
      const result = await mutation.mutateAsync(
        frequency === "all" ? undefined : (frequency as BillingFrequency)
      );
      toast.success(
        t("billingRuns.runSuccess", { count: result.receipts_generated })
      );
      setOpen(false);
    } catch {
      toast.error(t("toast.error.generic"));
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>{t("billingRuns.runNow")}</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("billingRuns.runNowTitle")}</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">{t("billingRuns.runNowDesc")}</p>
        <div className="space-y-2">
          <label className="text-sm font-medium">{t("billingRuns.frequencyPrompt")}</label>
          <Select value={frequency} onValueChange={setFrequency}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("billingRuns.frequencyValue.all")}</SelectItem>
              <SelectItem value="monthly">{t("billingRuns.frequencyValue.monthly")}</SelectItem>
              <SelectItem value="quarterly">{t("billingRuns.frequencyValue.quarterly")}</SelectItem>
              <SelectItem value="annual">{t("billingRuns.frequencyValue.annual")}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button onClick={handleRun} disabled={mutation.isPending} className="w-full">
          {mutation.isPending ? t("common.loading") : t("billingRuns.run")}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
