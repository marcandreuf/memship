"use client";

import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useFormatters } from "@/hooks/use-formatters";
import {
  useMembershipQuote,
  usePurchaseMembership,
} from "../hooks/use-membership-purchase";
import type { MembershipTypeData } from "../services/members-api";
import type { MembershipPurchaseData } from "../services/membership-purchase-api";

interface PurchasePlanDialogProps {
  plan: MembershipTypeData | null;
  onClose: () => void;
  onPurchased: (purchase: MembershipPurchaseData) => void;
}

function Line({
  label,
  value,
  strong = false,
}: {
  label: string;
  value: string;
  strong?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className={strong ? "text-sm font-medium" : "text-sm text-muted-foreground"}>
        {label}
      </dt>
      <dd className={`font-mono ${strong ? "text-base font-semibold" : "text-sm"}`}>
        {value}
      </dd>
    </div>
  );
}

/**
 * Confirm buying a plan: what it costs today, and what happens next.
 *
 * Every figure comes from the quote endpoint. The browser never adds VAT to the
 * advertised price — the rate lives on the `membership-{slug}` concept and an
 * admin can change it, so a locally computed total would disagree with the
 * receipt the member is then asked to pay.
 *
 * The dialog refuses to hide two things the member would otherwise discover
 * afterwards: that a first charge covering part of a period is smaller than the
 * plan price and the full period lands at the next boundary, and that nothing
 * is granted until the receipt is paid.
 */
export function PurchasePlanDialog({
  plan,
  onClose,
  onPurchased,
}: PurchasePlanDialogProps) {
  const t = useTranslations();
  const { formatCurrency, formatDate } = useFormatters();
  const { data: quote, isLoading, error } = useMembershipQuote(plan?.id ?? null);
  const purchase = usePurchaseMembership();

  async function handleConfirm() {
    if (!plan) return;
    try {
      const result = await purchase.mutateAsync(plan.id);
      toast.success(t("membership.purchaseRaised"));
      onPurchased(result);
    } catch {
      /* global handler shows the error toast */
    }
  }

  return (
    <Dialog open={plan != null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("membership.confirmPurchaseTitle")}</DialogTitle>
          <DialogDescription>
            {plan?.name}
            {plan ? ` · ${t(`membership.frequency.${plan.billing_frequency}`)}` : ""}
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        ) : error || !quote ? (
          <p className="text-sm text-destructive">{t("membership.quoteUnavailable")}</p>
        ) : (
          <div className="space-y-4">
            <dl className="space-y-1.5 rounded-md border p-3">
              <Line
                label={t("membership.baseAmount")}
                value={formatCurrency(quote.base_amount)}
              />
              <Line
                label={t("membership.vat", { rate: quote.vat_rate })}
                value={formatCurrency(quote.vat_amount)}
              />
              <Line
                label={t("membership.totalToday")}
                value={formatCurrency(quote.total_amount)}
                strong
              />
            </dl>

            {quote.is_prorated && (
              <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
                <p>
                  {t("membership.proratedExplain", {
                    monthsCharged: quote.months_charged ?? 0,
                    monthsInPeriod: quote.months_in_period ?? 0,
                    periodEnd: formatDate(quote.period_end),
                    fullPrice: formatCurrency(quote.full_price),
                  })}
                </p>
                <p className="mt-1 text-muted-foreground">
                  {t("membership.proratedNextCharge", {
                    fullPrice: formatCurrency(quote.full_price),
                  })}
                </p>
              </div>
            )}

            <p className="text-sm text-muted-foreground">
              {t("membership.notGrantedUntilPaid")}
            </p>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={purchase.isPending}>
            {t("common.cancel")}
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={!quote || isLoading || purchase.isPending}
          >
            {purchase.isPending ? t("common.loading") : t("membership.confirmPurchase")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
