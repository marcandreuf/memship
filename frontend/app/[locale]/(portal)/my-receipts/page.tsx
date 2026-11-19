"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import { CreditCard, Download } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Tooltip, TooltipContent, TooltipTrigger,
} from "@/components/ui/tooltip";
import { Pagination } from "@/components/entity/pagination";
import { TableSkeleton } from "@/components/ui/skeletons";
import { useFormatters } from "@/hooks/use-formatters";
import { useMyReceipts, useStripeCheckout } from "@/features/receipts/hooks/use-receipts";
import type { ReceiptData } from "@/features/receipts/services/receipts-api";
import { memberReceiptStatusLabel } from "@/features/receipts/lib/member-status";
import { RedsysPayButton } from "@/features/receipts/components/redsys-pay-button";
import { useActivePaymentMethods } from "@/features/settings/hooks/use-payment-providers";
import { usePageParam } from "@/hooks/use-url-state";
import { RECEIPT_STATUS_VARIANTS } from "@/lib/status-variants";

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
  const { data: activeMethods } = useActivePaymentMethods();
  const activeTypes = new Set((activeMethods || []).map((m) => m.provider_type));
  const stripeActive = activeTypes.has("stripe");
  const redsysActive = activeTypes.has("redsys");
  // Bizum is a method of the Redsys provider, not a provider of its own, and the
  // bank enables it per terminal — so it is offered only where the endpoint says
  // the administrator has turned it on (#405).
  const bizumActive = (activeMethods || []).some(
    (m) => m.provider_type === "redsys" && m.methods?.includes("bizum")
  );
  // A pay-to-confirm seat is paid only by what its activity accepts (#591).
  const accepts = (r: ReceiptData, method: string) =>
    !r.allowed_methods || r.allowed_methods.includes(method);

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
              <TableHead>{t("receipts.dueDate")}</TableHead>
              <TableHead>{t("receipts.paymentDate")}</TableHead>
              <TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((r) => {
              const statusLabel = memberReceiptStatusLabel(t, r.status);
              const payable = ["emitted", "overdue"].includes(r.status);
              return (
                <TableRow key={r.id}>
                  <TableCell className="font-mono text-sm">{r.receipt_number}</TableCell>
                  <TableCell className="max-w-[200px] truncate">{r.description}</TableCell>
                  <TableCell className="text-right font-mono">{formatCurrency(r.total_amount)}</TableCell>
                  <TableCell>
                    <Badge variant={RECEIPT_STATUS_VARIANTS[r.status] || "outline"}>{statusLabel}</Badge>
                  </TableCell>
                  <TableCell className="text-sm">{formatDate(r.emission_date)}</TableCell>
                  <TableCell className="text-sm">{payable && r.due_date ? formatDate(r.due_date) : "—"}</TableCell>
                  <TableCell className="text-sm">{formatDate(r.payment_date)}</TableCell>
                  <TableCell>
                    <div className="flex gap-2 flex-wrap">
                      {payable && (
                        <>
                          {stripeActive && accepts(r, "card") && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  size="icon"
                                  onClick={() => handlePayNow(r.id)}
                                  disabled={stripeCheckoutMutation.isPending}
                                  aria-label={t("receipts.payNow")}
                                >
                                  <CreditCard className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>{t("receipts.payNow")}</TooltipContent>
                            </Tooltip>
                          )}
                          {redsysActive && accepts(r, "card") && (
                            <RedsysPayButton receiptId={r.id} method="card" />
                          )}
                          {bizumActive && accepts(r, "bizum") && (
                            <RedsysPayButton receiptId={r.id} method="bizum" variant="outline" />
                          )}
                        </>
                      )}
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button variant="outline" size="icon" asChild>
                            <a
                              href={`/api/receipts/${r.id}/pdf`}
                              target="_blank"
                              rel="noopener noreferrer"
                              aria-label={t("receipts.downloadPdf")}
                            >
                              <Download className="h-4 w-4" />
                            </a>
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>{t("receipts.downloadPdf")}</TooltipContent>
                      </Tooltip>
                    </div>
                    {payable && r.bank_details && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        {t("receipts.payByTransfer", { bank: r.bank_details })}
                      </p>
                    )}
                    {payable && r.allowed_methods?.includes("cash") && (
                      <p className="mt-1 text-xs text-muted-foreground">{t("receipts.payInCash")}</p>
                    )}
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
