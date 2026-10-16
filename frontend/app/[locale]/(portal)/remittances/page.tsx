"use client";

import { useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import { Link, useRouter } from "@/lib/i18n/routing";
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
import { Checkbox } from "@/components/ui/checkbox";
import { Pagination } from "@/components/entity/pagination";
import { PageInfo } from "@/components/page-info";
import { TableSkeleton } from "@/components/ui/skeletons";
import { toast } from "sonner";
import {
  useRemittances,
  useCreateRemittance,
  useEligibleReceipts,
} from "@/features/remittances/hooks/use-remittances";
import { usePageParam, useStatusParam } from "@/hooks/use-url-state";
import { useFormatters } from "@/hooks/use-formatters";
import { usePermissions } from "@/features/auth/hooks/use-permissions";

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  draft: "outline",
  ready: "secondary",
  submitted: "secondary",
  processed: "default",
  closed: "default",
  cancelled: "destructive",
};

function StatusBadge({ status, t }: { status: string; t: (key: string) => string }) {
  const label = t(`remittances.status${status.charAt(0).toUpperCase() + status.slice(1)}`);
  return <Badge variant={STATUS_VARIANTS[status] || "outline"}>{label}</Badge>;
}

export default function RemittancesPage() {
  const t = useTranslations();
  const { has } = usePermissions();
  const canWrite = has("billing.write");
  const router = useRouter();
  const [page, setPage] = usePageParam();
  const [statusFilter, setStatusFilter] = useStatusParam();
  const [createOpen, setCreateOpen] = useState(false);

  const params = useMemo(() => {
    const p = new URLSearchParams();
    p.set("page", String(page));
    p.set("per_page", "20");
    if (statusFilter) p.set("status", statusFilter);
    return p;
  }, [page, statusFilter]);

  const { data, isLoading } = useRemittances(params);
  const { formatCurrency, formatDate } = useFormatters();

  if (isLoading) return <TableSkeleton />;

  const items = data?.items || [];
  const meta = data?.meta || { page: 1, per_page: 20, total: 0, total_pages: 1 };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold">{t("remittances.title")}</h1>
          <PageInfo text={t("remittances.info")} />
        </div>
        {canWrite && (
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button>{t("remittances.createRemittance")}</Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-2xl">
              <DialogHeader>
                <DialogTitle>{t("remittances.createRemittance")}</DialogTitle>
              </DialogHeader>
              <CreateRemittanceForm onSuccess={() => setCreateOpen(false)} />
            </DialogContent>
          </Dialog>
        )}
      </div>

      <div className="flex items-center gap-3">
        <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v === "all" ? "" : v); setPage(1); }}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder={t("remittances.status")} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("common.all")}</SelectItem>
            <SelectItem value="draft">{t("remittances.statusDraft")}</SelectItem>
            <SelectItem value="ready">{t("remittances.statusReady")}</SelectItem>
            <SelectItem value="submitted">{t("remittances.statusSubmitted")}</SelectItem>
            <SelectItem value="processed">{t("remittances.statusProcessed")}</SelectItem>
            <SelectItem value="closed">{t("remittances.statusClosed")}</SelectItem>
            <SelectItem value="cancelled">{t("remittances.statusCancelled")}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {items.length === 0 ? (
        <div className="py-8 text-center text-muted-foreground">{t("remittances.noRemittances")}</div>
      ) : (
        <>
        <div className="hidden @3xl:block rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("remittances.remittanceNumber")}</TableHead>
              <TableHead>{t("remittances.emissionDate")}</TableHead>
              <TableHead>{t("remittances.dueDate")}</TableHead>
              <TableHead className="text-center">{t("remittances.receiptCount")}</TableHead>
              <TableHead className="text-right">{t("remittances.totalAmount")}</TableHead>
              <TableHead>{t("remittances.status")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((r) => (
              <TableRow
                key={r.id}
                className="cursor-pointer hover:bg-muted/50"
                onClick={() => router.push(`/remittances/${r.id}`)}
              >
                <TableCell className="font-mono text-sm">{r.remittance_number}</TableCell>
                <TableCell className="text-sm">{formatDate(r.emission_date)}</TableCell>
                <TableCell className="text-sm">{formatDate(r.due_date)}</TableCell>
                <TableCell className="text-center">{r.receipt_count}</TableCell>
                <TableCell className="text-right font-mono">{formatCurrency(r.total_amount)}</TableCell>
                <TableCell><StatusBadge status={r.status} t={t} /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        </div>

        <div className="space-y-3 @3xl:hidden">
          {items.map((r) => (
            <Link
              key={r.id}
              href={`/remittances/${r.id}`}
              className="block rounded-lg border p-4 hover:bg-accent transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-mono text-sm">{r.remittance_number}</p>
                  <p className="text-sm text-muted-foreground">
                    {formatDate(r.emission_date)} → {formatDate(r.due_date)}
                  </p>
                </div>
                <StatusBadge status={r.status} t={t} />
              </div>
              <div className="mt-1 flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                  {t("remittances.receiptCount")}: {r.receipt_count}
                </span>
                <span className="font-mono">{formatCurrency(r.total_amount)}</span>
              </div>
            </Link>
          ))}
        </div>
        </>
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

// The collection date, in the two shapes this form needs it. Both read the
// browser's local day rather than UTC: a date input is a local calendar date,
// and `toISOString` would hand back yesterday for anyone east of Greenwich.
function localIsoDate(value: Date): string {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(
    value.getDate()
  ).padStart(2, "0")}`;
}

function isWeekend(iso: string): boolean {
  if (!iso) return false;
  const day = new Date(`${iso}T00:00:00`).getDay();
  return day === 0 || day === 6;
}

function CreateRemittanceForm({ onSuccess }: { onSuccess: () => void }) {
  const t = useTranslations();
  const { formatCurrency } = useFormatters();
  const mutation = useCreateRemittance();
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [dueDate, setDueDate] = useState("");
  const [notes, setNotes] = useState("");
  const todayIso = localIsoDate(new Date());

  // What can be batched is the backend's rule, not this dialog's: it also
  // covers the document type and the member's mandate, and it includes overdue
  // receipts — which this screen offers in writing and never used to fetch.
  const [page, setPage] = useState(1);
  const receiptParams = useMemo(() => {
    const p = new URLSearchParams();
    p.set("per_page", "100");
    p.set("page", String(page));
    return p;
  }, [page]);
  const { data: receiptData, isLoading } = useEligibleReceipts(receiptParams);
  const eligibleReceipts = receiptData?.items || [];
  const totalEligible = receiptData?.meta?.total ?? eligibleReceipts.length;
  const totalPages = receiptData?.meta?.total_pages ?? 1;

  function toggleReceipt(id: number) {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  }

  // `Number(...)` rather than a bare `+`: the API has sent this field as a
  // string before now, and concatenating gives a wrong total instead of an
  // error (#364).
  const selectedTotal = eligibleReceipts
    .filter((r) => selectedIds.includes(r.id))
    .reduce((sum, r) => sum + Number(r.total_amount), 0);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (selectedIds.length === 0 || !dueDate) return;
    try {
      await mutation.mutateAsync({
        receipt_ids: selectedIds,
        due_date: dueDate,
        notes: notes || undefined,
      });
      toast.success(t("toast.success.saved"));
      onSuccess();
    } catch {
      // Reported once by the mutation cache in react-query-provider (#378).
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <p className="text-sm text-muted-foreground">{t("remittances.selectReceiptsDesc")}</p>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      ) : eligibleReceipts.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("remittances.noReceipts")}</p>
      ) : (
        <div className="max-h-60 overflow-y-auto border rounded-md">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10"></TableHead>
                <TableHead>{t("receipts.receiptNumber")}</TableHead>
                <TableHead>{t("receipts.member")}</TableHead>
                <TableHead className="text-right">{t("receipts.total")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {eligibleReceipts.map((r) => (
                <TableRow key={r.id} className="cursor-pointer" onClick={() => toggleReceipt(r.id)}>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <Checkbox checked={selectedIds.includes(r.id)} onCheckedChange={() => toggleReceipt(r.id)} />
                  </TableCell>
                  <TableCell className="font-mono text-sm">{r.receipt_number}</TableCell>
                  <TableCell>
                    {r.member_name || r.member_number ? (
                      <>
                        {r.member_name}
                        {r.member_number && (
                          <span className="ml-2 font-mono text-xs text-muted-foreground">
                            {r.member_number}
                          </span>
                        )}
                      </>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                  <TableCell className="text-right font-mono">{formatCurrency(r.total_amount)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* The dialog used to ask for 100 rows and show whatever came back, so a
          club with more emitted receipts than that silently could not reach
          them. */}
      <Pagination
        page={page}
        totalPages={totalPages}
        total={totalEligible}
        perPage={100}
        onPageChange={setPage}
      />

      {selectedIds.length > 0 && (
        <div className="text-sm font-medium">
          {t("remittances.selectedCount", { count: selectedIds.length })}
          {" — "}
          {t("remittances.selectedTotal", { total: formatCurrency(selectedTotal) })}
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="text-sm font-medium">{t("remittances.dueDate")}</label>
          {/* `min` stops the picker offering a date the bank cannot act on;
              the API refuses one anyway (#395). No default is set, because any
              lead time memship chose would be a claim about a particular
              bank's cut-off that it has no way to know. */}
          <Input
            type="date"
            min={todayIso}
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
          />
          {/* A warning, not a refusal: a weekend is not a settlement day, but
              the TARGET holiday calendar is not something memship carries, so
              refusing on the weekend alone would be half a rule. */}
          {isWeekend(dueDate) && (
            <p className="mt-1 text-xs text-muted-foreground">
              {t("remittances.dueDateWeekend")}
            </p>
          )}
        </div>
        <div>
          <label className="text-sm font-medium">{t("remittances.notes")}</label>
          <Input value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
      </div>

      <Button type="submit" disabled={selectedIds.length === 0 || !dueDate || mutation.isPending} className="w-full">
        {mutation.isPending ? t("common.loading") : t("remittances.createRemittance")}
      </Button>
    </form>
  );
}
