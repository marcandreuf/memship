"use client";

import { useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { SearchInput } from "@/components/entity/search-input";
import { Pagination } from "@/components/entity/pagination";
import { TableSkeleton } from "@/components/ui/skeletons";
import { toast } from "sonner";
import { useReceipts, useGenerateMembershipFees } from "@/features/receipts/hooks/use-receipts";
import { useSearchParam, usePageParam, useStatusParam } from "@/hooks/use-url-state";
import { useFormatters } from "@/hooks/use-formatters";
import type { ReceiptData } from "@/features/receipts/services/receipts-api";

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  new: "outline",
  pending: "secondary",
  emitted: "secondary",
  paid: "default",
  returned: "destructive",
  cancelled: "destructive",
  overdue: "destructive",
};

function StatusBadge({ status, t }: { status: string; t: (key: string) => string }) {
  const label = t(`receipts.status${status.charAt(0).toUpperCase() + status.slice(1)}`);
  return <Badge variant={STATUS_VARIANTS[status] || "outline"}>{label}</Badge>;
}

function OriginBadge({ origin, t }: { origin: string; t: (key: string) => string }) {
  const label = t(`receipts.origin${origin.charAt(0).toUpperCase() + origin.slice(1)}`);
  return <Badge variant="outline">{label}</Badge>;
}


export default function ReceiptsPage() {
  const t = useTranslations();
  const router = useRouter();
  const [page, setPage] = usePageParam();
  const [search, setSearch] = useSearchParam();
  const [statusFilter, setStatusFilter] = useStatusParam();
  const [generateOpen, setGenerateOpen] = useState(false);

  const params = useMemo(() => {
    const p = new URLSearchParams();
    p.set("page", String(page));
    p.set("per_page", "20");
    if (search) p.set("search", search);
    if (statusFilter) p.set("status", statusFilter);
    return p;
  }, [page, search, statusFilter]);

  const { data, isLoading } = useReceipts(params);
  const { formatCurrency, formatDate } = useFormatters();

  if (isLoading) return <TableSkeleton />;

  const items = data?.items || [];
  const meta = data?.meta || { page: 1, per_page: 20, total: 0, total_pages: 1 };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("receipts.title")}</h1>
        <GenerateFeesButton t={t} />
      </div>

      <div className="flex items-center gap-3">
        <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder={t("common.search")} />
        <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v === "all" ? "" : v); setPage(1); }}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder={t("receipts.status")} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("common.all")}</SelectItem>
            <SelectItem value="pending">{t("receipts.statusPending")}</SelectItem>
            <SelectItem value="emitted">{t("receipts.statusEmitted")}</SelectItem>
            <SelectItem value="paid">{t("receipts.statusPaid")}</SelectItem>
            <SelectItem value="returned">{t("receipts.statusReturned")}</SelectItem>
            <SelectItem value="overdue">{t("receipts.statusOverdue")}</SelectItem>
            <SelectItem value="cancelled">{t("receipts.statusCancelled")}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground py-8 text-center">{t("receipts.noReceipts")}</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("receipts.receiptNumber")}</TableHead>
              <TableHead>{t("receipts.member")}</TableHead>
              <TableHead>{t("receipts.description")}</TableHead>
              <TableHead className="text-right">{t("receipts.total")}</TableHead>
              <TableHead>{t("receipts.status")}</TableHead>
              <TableHead>{t("receipts.origin")}</TableHead>
              <TableHead>{t("receipts.emissionDate")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((r: ReceiptData) => (
              <TableRow
                key={r.id}
                className="cursor-pointer hover:bg-muted/50"
                onClick={() => router.push(`/receipts/${r.id}`)}
              >
                <TableCell className="font-mono text-sm">{r.receipt_number}</TableCell>
                <TableCell>{r.member_name || "—"}</TableCell>
                <TableCell className="max-w-[200px] truncate">{r.description}</TableCell>
                <TableCell className="text-right font-mono">{formatCurrency(r.total_amount)}</TableCell>
                <TableCell><StatusBadge status={r.status} t={t} /></TableCell>
                <TableCell><OriginBadge origin={r.origin} t={t} /></TableCell>
                <TableCell className="text-sm">{formatDate(r.emission_date)}</TableCell>
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

function GenerateFeesButton({ t }: { t: (key: string) => string }) {
  const [open, setOpen] = useState(false);
  const mutation = useGenerateMembershipFees();
  const today = new Date().toISOString().split("T")[0];
  const yearStart = `${new Date().getFullYear()}-01-01`;
  const yearEnd = `${new Date().getFullYear()}-12-31`;

  const form = useForm({
    defaultValues: {
      billing_period_start: yearStart,
      billing_period_end: yearEnd,
      emission_date: today,
      due_date: "",
    },
  });

  async function onSubmit(data: Record<string, string>) {
    const payload: Record<string, unknown> = {
      billing_period_start: data.billing_period_start,
      billing_period_end: data.billing_period_end,
      emission_date: data.emission_date,
    };
    if (data.due_date) payload.due_date = data.due_date;

    try {
      const result = await mutation.mutateAsync(payload);
      toast.success(t("receipts.generated").replace("{count}", String(result.generated)));
      setOpen(false);
    } catch {
      toast.error(t("toast.error.generic"));
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">{t("receipts.generateFees")}</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("receipts.generateFees")}</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">{t("receipts.generateFeesDesc")}</p>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="text-sm font-medium">{t("receipts.billingPeriodStart")}</label>
              <Input type="date" {...form.register("billing_period_start")} />
            </div>
            <div>
              <label className="text-sm font-medium">{t("receipts.billingPeriodEnd")}</label>
              <Input type="date" {...form.register("billing_period_end")} />
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="text-sm font-medium">{t("receipts.emissionDate")}</label>
              <Input type="date" {...form.register("emission_date")} />
            </div>
            <div>
              <label className="text-sm font-medium">{t("receipts.dueDate")}</label>
              <Input type="date" {...form.register("due_date")} />
            </div>
          </div>
          <Button type="submit" disabled={mutation.isPending} className="w-full">
            {mutation.isPending ? t("common.loading") : t("receipts.generateFees")}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
