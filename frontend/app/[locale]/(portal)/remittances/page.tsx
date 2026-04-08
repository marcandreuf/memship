"use client";

import { useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
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
import { TableSkeleton } from "@/components/ui/skeletons";
import { toast } from "sonner";
import { useRemittances, useCreateRemittance } from "@/features/remittances/hooks/use-remittances";
import { useReceipts } from "@/features/receipts/hooks/use-receipts";
import { usePageParam, useStatusParam } from "@/hooks/use-url-state";
import { useFormatters } from "@/hooks/use-formatters";

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
        <h1 className="text-2xl font-bold">{t("remittances.title")}</h1>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button>{t("remittances.createRemittance")}</Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>{t("remittances.createRemittance")}</DialogTitle>
            </DialogHeader>
            <CreateRemittanceForm onSuccess={() => setCreateOpen(false)} />
          </DialogContent>
        </Dialog>
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
        <p className="text-sm text-muted-foreground py-8 text-center">{t("remittances.noRemittances")}</p>
      ) : (
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

function CreateRemittanceForm({ onSuccess }: { onSuccess: () => void }) {
  const t = useTranslations();
  const mutation = useCreateRemittance();
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [dueDate, setDueDate] = useState("");
  const [notes, setNotes] = useState("");

  // Fetch eligible receipts (emitted/overdue, batchable)
  const receiptParams = useMemo(() => {
    const p = new URLSearchParams();
    p.set("per_page", "100");
    p.set("status", "emitted");
    return p;
  }, []);
  const { data: receiptData, isLoading } = useReceipts(receiptParams);
  const eligibleReceipts = (receiptData?.items || []).filter(
    (r) => r.is_batchable && !r.remittance_id
  );

  function toggleReceipt(id: number) {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  }

  const selectedTotal = eligibleReceipts
    .filter((r) => selectedIds.includes(r.id))
    .reduce((sum, r) => sum + r.total_amount, 0);

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
      toast.error(t("toast.error.generic"));
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
                  <TableCell>{r.member_name || "—"}</TableCell>
                  <TableCell className="text-right font-mono">{r.total_amount.toFixed(2)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {selectedIds.length > 0 && (
        <div className="text-sm font-medium">
          {t("remittances.selectedCount", { count: selectedIds.length })}
          {" — "}
          {t("remittances.selectedTotal", { total: selectedTotal.toFixed(2) })}
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="text-sm font-medium">{t("remittances.dueDate")}</label>
          <Input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
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
