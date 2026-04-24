"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Pagination } from "@/components/entity/pagination";
import { TableSkeleton } from "@/components/ui/skeletons";
import { useFormatters } from "@/hooks/use-formatters";
import { useMyReceipts, useStripeCheckout } from "@/features/receipts/hooks/use-receipts";
import { RedsysPayButton } from "@/features/receipts/components/redsys-pay-button";
import { usePageParam } from "@/hooks/use-url-state";

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  new: "outline",
  pending: "secondary",
  emitted: "secondary",
  paid: "default",
  returned: "destructive",
  cancelled: "destructive",
  overdue: "destructive",
};

export default function MyReceiptsPage() {
  const t = useTranslations();
  const [page, setPage] = usePageParam();

  const params = useMemo(() => {
    const p = new URLSearchParams();
    p.set("page", String(page));
    p.set("per_page", "20");
    return p;
  }, [page]);

  const { data, isLoading } = useMyReceipts(params);
  const { formatCurrency, formatDate } = useFormatters();
  const stripeCheckoutMutation = useStripeCheckout();

  async function handlePayNow(receiptId: number) {
    try {
      const result = await stripeCheckoutMutation.mutateAsync(receiptId);
      window.location.href = result.redirect_url;
    } catch { /* global handler */ }
  }

  if (isLoading) return <TableSkeleton />;

  const items = data?.items || [];
  const meta = data?.meta || { page: 1, per_page: 20, total: 0, total_pages: 1 };

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">{t("receipts.myReceipts")}</h1>

      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground py-8 text-center">{t("receipts.noReceipts")}</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("receipts.receiptNumber")}</TableHead>
              <TableHead>{t("receipts.description")}</TableHead>
              <TableHead className="text-right">{t("receipts.total")}</TableHead>
              <TableHead>{t("receipts.status")}</TableHead>
              <TableHead>{t("receipts.emissionDate")}</TableHead>
              <TableHead>{t("receipts.paymentDate")}</TableHead>
              <TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((r) => {
              const statusLabel = t(`receipts.status${r.status.charAt(0).toUpperCase() + r.status.slice(1)}`);
              return (
                <TableRow key={r.id}>
                  <TableCell className="font-mono text-sm">{r.receipt_number}</TableCell>
                  <TableCell className="max-w-[200px] truncate">{r.description}</TableCell>
                  <TableCell className="text-right font-mono">{formatCurrency(r.total_amount)}</TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANTS[r.status] || "outline"}>{statusLabel}</Badge>
                  </TableCell>
                  <TableCell className="text-sm">{formatDate(r.emission_date)}</TableCell>
                  <TableCell className="text-sm">{formatDate(r.payment_date)}</TableCell>
                  <TableCell>
                    <div className="flex gap-2 flex-wrap">
                      {["emitted", "overdue"].includes(r.status) && (
                        <>
                          <Button
                            size="sm"
                            onClick={() => handlePayNow(r.id)}
                            disabled={stripeCheckoutMutation.isPending}
                          >
                            {t("receipts.payNow")}
                          </Button>
                          <RedsysPayButton receiptId={r.id} method="card" variant="secondary" />
                          <RedsysPayButton receiptId={r.id} method="bizum" variant="outline" />
                        </>
                      )}
                      <Button variant="outline" size="sm" asChild>
                        <a href={`/api/receipts/${r.id}/pdf`} target="_blank" rel="noopener noreferrer">
                          {t("receipts.downloadPdf")}
                        </a>
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
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
