"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Link, useRouter } from "@/lib/i18n/routing";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PageInfo } from "@/components/page-info";
import { Pagination } from "@/components/entity/pagination";
import { TableSkeleton } from "@/components/ui/skeletons";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { useLocaleDate } from "@/hooks/use-locale-date";
import { useFormatters } from "@/hooks/use-formatters";
import { usePermissions } from "@/features/auth/hooks/use-permissions";
import { useMarkRefundReturned, useRefunds } from "@/features/seats/hooks/use-seats";
import { seatOwnerHref, type RefundData } from "@/features/seats/services/seats-api";

type RefundFilter = "due" | "returned";

export default function RefundsPage() {
  const t = useTranslations();
  const router = useRouter();
  const { has } = usePermissions();
  const { shortDate } = useLocaleDate();
  const [filter, setFilter] = useState<RefundFilter>("due");
  const [page, setPage] = useState(1);
  const { formatCurrency } = useFormatters();
  const { data, isLoading, isError } = useRefunds({ page, refund_status: filter });
  const markReturned = useMarkRefundReturned();
  const [confirmDialog, confirm] = useConfirmDialog();
  const canMark = filter === "due" && has("billing.write");

  function handleMarkReturned(refund: RefundData) {
    confirm({
      title: t("activities.refunds.confirmMarkReturned"),
      description: t("activities.refunds.confirmMarkReturnedDescription"),
      confirmLabel: t("activities.refunds.markReturned"),
      onConfirm: async () => {
        try {
          await markReturned.mutateAsync({ kind: refund.kind, seatId: refund.seat_id });
          toast.success(t("toast.success.updated"));
        } catch { /* global handler shows error toast */ }
      },
    });
  }

  const method = (r: RefundData) =>
    r.payment_method
      ? t(`receipts.method${r.payment_method.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join("")}`)
      : "—";
  const kind = (r: RefundData) =>
    t(r.kind === "booking" ? "activities.refunds.kindBooking" : "activities.refunds.kindRegistration");
  const when = (r: RefundData) => {
    const at = filter === "due" ? r.cancelled_at : r.refund_returned_at;
    return at ? shortDate(at) : "—";
  };

  return (
    <div className="space-y-4">
      {confirmDialog}
      <div className="flex items-center gap-2">
        <h1 className="text-2xl font-bold">{t("activities.refunds.title")}</h1>
        <PageInfo text={t("activities.refunds.info")} />
      </div>

      <Select
        value={filter}
        onValueChange={(v) => {
          setFilter(v as RefundFilter);
          setPage(1);
        }}
      >
        <SelectTrigger className="sm:w-48">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="due">{t("activities.refunds.due")}</SelectItem>
          <SelectItem value="returned">{t("activities.refunds.returned")}</SelectItem>
        </SelectContent>
      </Select>

      {isLoading ? (
        <TableSkeleton rows={4} columns={7} />
      ) : isError ? (
        /* Not the empty state: a failed request read as "no refunds" and hid
           a missing proxy route for the whole of #591's validation. */
        <div role="alert" className="py-8 text-center text-destructive">
          {t("activities.refunds.loadError")}
        </div>
      ) : !data?.items.length ? (
        <div className="py-8 text-center text-muted-foreground">{t("activities.refunds.empty")}</div>
      ) : (
        <>
          <div className="hidden md:block rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("activities.refunds.member")}</TableHead>
                  <TableHead>{t("activities.refunds.kind")}</TableHead>
                  <TableHead>{t("activities.refunds.activity")}</TableHead>
                  <TableHead>{t("activities.refunds.amount")}</TableHead>
                  <TableHead>{t("activities.refunds.method")}</TableHead>
                  <TableHead>{t("activities.refunds.reference")}</TableHead>
                  <TableHead>
                    {filter === "due" ? t("activities.refunds.cancelledAt") : t("activities.refunds.returnedAt")}
                  </TableHead>
                  {canMark && <TableHead>{t("common.actions")}</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((r) => (
                  <TableRow
                    key={`${r.kind}-${r.seat_id}`}
                    className="cursor-pointer"
                    onClick={() => router.push(seatOwnerHref(r))}
                  >
                    <TableCell className="font-medium">{r.member_name ?? "—"}</TableCell>
                    <TableCell>{kind(r)}</TableCell>
                    <TableCell>
                      <Link
                        href={seatOwnerHref(r)}
                        className="hover:underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {r.owner_name}
                      </Link>
                    </TableCell>
                    <TableCell>{formatCurrency(r.amount)}</TableCell>
                    <TableCell>{method(r)}</TableCell>
                    <TableCell className="font-mono text-xs">{r.gateway_reference ?? r.receipt_number}</TableCell>
                    <TableCell>{when(r)}</TableCell>
                    {canMark && (
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <Button size="sm" variant="outline" onClick={() => handleMarkReturned(r)}>
                          {t("activities.refunds.markReturned")}
                        </Button>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <div className="space-y-3 md:hidden">
            {data.items.map((r) => (
              <div key={`${r.kind}-${r.seat_id}`} className="rounded-lg border p-4 space-y-1">
                <Link href={seatOwnerHref(r)} className="block">
                  <p className="font-medium">{r.member_name ?? "—"}</p>
                  <p className="text-sm text-muted-foreground">
                    {kind(r)} · {r.owner_name}
                  </p>
                  <p className="text-sm">
                    {formatCurrency(r.amount)} · {method(r)} · {when(r)}
                  </p>
                  <p className="font-mono text-xs text-muted-foreground">
                    {r.gateway_reference ?? r.receipt_number}
                  </p>
                </Link>
                {canMark && (
                  <Button size="sm" variant="outline" onClick={() => handleMarkReturned(r)}>
                    {t("activities.refunds.markReturned")}
                  </Button>
                )}
              </div>
            ))}
          </div>

          <Pagination
            page={page}
            totalPages={data.meta.total_pages}
            total={data.meta.total}
            perPage={data.meta.per_page}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}
