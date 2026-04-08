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
import { SearchInput } from "@/components/entity/search-input";
import { Pagination } from "@/components/entity/pagination";
import { TableSkeleton } from "@/components/ui/skeletons";
import { toast } from "sonner";
import { useMandates, useCreateMandate } from "@/features/mandates/hooks/use-mandates";
import { useSearchParam, usePageParam, useStatusParam } from "@/hooks/use-url-state";
import { useFormatters } from "@/hooks/use-formatters";

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  active: "default",
  cancelled: "destructive",
  expired: "secondary",
};

function StatusBadge({ status, t }: { status: string; t: (key: string) => string }) {
  const label = t(`mandates.status${status.charAt(0).toUpperCase() + status.slice(1)}`);
  return <Badge variant={STATUS_VARIANTS[status] || "outline"}>{label}</Badge>;
}

export default function MandatesPage() {
  const t = useTranslations();
  const router = useRouter();
  const [page, setPage] = usePageParam();
  const [search, setSearch] = useSearchParam();
  const [statusFilter, setStatusFilter] = useStatusParam();
  const [createOpen, setCreateOpen] = useState(false);

  const params = useMemo(() => {
    const p = new URLSearchParams();
    p.set("page", String(page));
    p.set("per_page", "20");
    if (search) p.set("search", search);
    if (statusFilter) p.set("status", statusFilter);
    return p;
  }, [page, search, statusFilter]);

  const { data, isLoading } = useMandates(params);
  const { formatDate } = useFormatters();

  if (isLoading) return <TableSkeleton />;

  const items = data?.items || [];
  const meta = data?.meta || { page: 1, per_page: 20, total: 0, total_pages: 1 };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("mandates.title")}</h1>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button>{t("mandates.createMandate")}</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t("mandates.createMandate")}</DialogTitle>
            </DialogHeader>
            <CreateMandateForm t={t} onSuccess={() => setCreateOpen(false)} />
          </DialogContent>
        </Dialog>
      </div>

      <div className="flex items-center gap-3">
        <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder={t("common.search")} />
        <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v === "all" ? "" : v); setPage(1); }}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder={t("mandates.status")} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("common.all")}</SelectItem>
            <SelectItem value="active">{t("mandates.statusActive")}</SelectItem>
            <SelectItem value="cancelled">{t("mandates.statusCancelled")}</SelectItem>
            <SelectItem value="expired">{t("mandates.statusExpired")}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground py-8 text-center">{t("mandates.noMandates")}</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("mandates.mandateReference")}</TableHead>
              <TableHead>{t("mandates.debtorName")}</TableHead>
              <TableHead>{t("mandates.debtorIban")}</TableHead>
              <TableHead>{t("mandates.status")}</TableHead>
              <TableHead>{t("mandates.signedAt")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((m) => (
              <TableRow
                key={m.id}
                className="cursor-pointer hover:bg-muted/50"
                onClick={() => router.push(`/mandates/${m.id}`)}
              >
                <TableCell className="font-mono text-sm">{m.mandate_reference}</TableCell>
                <TableCell>{m.debtor_name}</TableCell>
                <TableCell className="font-mono text-sm">{m.debtor_iban}</TableCell>
                <TableCell><StatusBadge status={m.status} t={t} /></TableCell>
                <TableCell className="text-sm">{formatDate(m.signed_at)}</TableCell>
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

function CreateMandateForm({ t, onSuccess }: { t: (key: string) => string; onSuccess: () => void }) {
  const mutation = useCreateMandate();
  const [memberId, setMemberId] = useState("");
  const [debtorName, setDebtorName] = useState("");
  const [debtorIban, setDebtorIban] = useState("");
  const [debtorBic, setDebtorBic] = useState("");
  const [signedAt, setSignedAt] = useState(new Date().toISOString().split("T")[0]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!memberId || !debtorName || !debtorIban || !signedAt) return;
    try {
      await mutation.mutateAsync({
        member_id: parseInt(memberId),
        debtor_name: debtorName,
        debtor_iban: debtorIban.toUpperCase().replace(/\s/g, ""),
        debtor_bic: debtorBic || undefined,
        signed_at: signedAt,
      });
      toast.success(t("toast.success.saved"));
      onSuccess();
    } catch {
      toast.error(t("toast.error.generic"));
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="text-sm font-medium">{t("mandates.member")} (ID)</label>
        <Input type="number" value={memberId} onChange={(e) => setMemberId(e.target.value)} placeholder="Member ID" />
      </div>
      <div>
        <label className="text-sm font-medium">{t("mandates.debtorName")}</label>
        <Input value={debtorName} onChange={(e) => setDebtorName(e.target.value)} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="text-sm font-medium">{t("mandates.debtorIban")}</label>
          <Input value={debtorIban} onChange={(e) => setDebtorIban(e.target.value)} placeholder="ES9121000418450200051332" className="font-mono" />
        </div>
        <div>
          <label className="text-sm font-medium">{t("mandates.debtorBic")}</label>
          <Input value={debtorBic} onChange={(e) => setDebtorBic(e.target.value)} placeholder="CAIXESBBXXX" className="font-mono" />
        </div>
      </div>
      <div>
        <label className="text-sm font-medium">{t("mandates.signedAt")}</label>
        <Input type="date" value={signedAt} onChange={(e) => setSignedAt(e.target.value)} />
      </div>
      <Button type="submit" disabled={!memberId || !debtorName || !debtorIban || mutation.isPending} className="w-full">
        {mutation.isPending ? t("common.loading") : t("mandates.createMandate")}
      </Button>
    </form>
  );
}
