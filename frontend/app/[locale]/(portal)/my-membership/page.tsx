"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { CreditCard } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PageInfo } from "@/components/page-info";
import { CardGridSkeleton, FormSkeleton } from "@/components/ui/skeletons";
import { useFormatters } from "@/hooks/use-formatters";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { useMember, useMembershipTypes } from "@/features/members/hooks/use-members";
import { PurchasePlanDialog } from "@/features/members/components/purchase-plan-dialog";
import type { MembershipTypeData } from "@/features/members/services/members-api";
import type { MembershipPurchaseData } from "@/features/members/services/membership-purchase-api";
import { useMyReceipts, useStripeCheckout } from "@/features/receipts/hooks/use-receipts";
import { RedsysPayButton } from "@/features/receipts/components/redsys-pay-button";
import { useActivePaymentMethods } from "@/features/settings/hooks/use-payment-providers";

/**
 * A purchase receipt still owes money in any of these. `paid` has already
 * granted the plan and `cancelled` was voided — by a newer purchase, or by the
 * nightly expiry of a checkout nobody completed.
 */
const OPEN_PURCHASE_STATUSES = new Set([
  "new",
  "pending",
  "emitted",
  "overdue",
  "returned",
]);

export default function MyMembershipPage() {
  const t = useTranslations();
  const { user } = useAuth();
  const { formatCurrency, formatDate } = useFormatters();

  const [selected, setSelected] = useState<MembershipTypeData | null>(null);
  // The purchase response, kept so the payment buttons appear the instant the
  // dialog closes rather than after the receipt list has refetched.
  const [justPurchased, setJustPurchased] = useState<MembershipPurchaseData | null>(null);

  const { data: member, isLoading: memberLoading } = useMember(user?.member_id || 0);
  const { data: plans, isLoading: plansLoading } = useMembershipTypes();

  // The open purchase sorts to the top of the member's own receipts — the list
  // is ordered by emission date and a purchase is emitted the day it is made —
  // so one page is enough to find it without a new endpoint.
  const receiptParams = useMemo(() => {
    const p = new URLSearchParams();
    p.set("page", "1");
    p.set("per_page", "50");
    return p;
  }, []);
  const { data: receipts } = useMyReceipts(receiptParams);

  const stripeCheckout = useStripeCheckout();
  const { data: activeMethods } = useActivePaymentMethods();
  const activeTypes = new Set((activeMethods || []).map((m) => m.provider_type));
  const stripeActive = activeTypes.has("stripe");
  const redsysActive = activeTypes.has("redsys");

  const openPurchase = useMemo(() => {
    const found = (receipts?.items || []).find(
      (r) =>
        r.purchased_membership_type_id != null &&
        OPEN_PURCHASE_STATUSES.has(r.status)
    );
    if (found) {
      return {
        receiptId: found.id,
        receiptNumber: found.receipt_number,
        planId: found.purchased_membership_type_id!,
        total: found.total_amount,
        dueDate: found.due_date,
      };
    }
    if (justPurchased) {
      return {
        receiptId: justPurchased.receipt_id,
        receiptNumber: justPurchased.receipt_number,
        planId: justPurchased.membership_type_id,
        total: justPurchased.total_amount,
        dueDate: justPurchased.due_date,
      };
    }
    return null;
  }, [receipts, justPurchased]);

  const planName = (id: number) =>
    (plans || []).find((p) => p.id === id)?.name ?? `#${id}`;

  // What the member can actually buy, mirroring what the purchase endpoint
  // accepts: an active plan that costs something and is not the one they hold.
  // Offering anything else would quote a price the server then refuses.
  const purchasable = useMemo(
    () =>
      (plans || []).filter(
        (p) =>
          p.is_active &&
          Number(p.base_price) > 0 &&
          p.id !== member?.membership_type_id
      ),
    [plans, member]
  );

  async function handleStripe(receiptId: number) {
    try {
      const result = await stripeCheckout.mutateAsync(receiptId);
      window.location.href = result.redirect_url;
    } catch {
      /* global handler */
    }
  }

  if (memberLoading || !member) return <FormSkeleton />;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h1 className="text-2xl font-bold">{t("membership.title")}</h1>
        <PageInfo text={t("membership.info")} />
      </div>

      {/* Current plan. `membership_reverted_from_name` is set only while the
          member is sitting on the free tier because a fee went unpaid, so it
          answers "why am I on this plan" in the same place as "which plan". */}
      <Card data-testid="current-plan">
        <CardContent className="space-y-2">
          <p className="text-xs text-muted-foreground">{t("membership.currentPlan")}</p>
          <p className="text-lg font-medium">
            {member.membership_type_name || t("membership.noPlan")}
          </p>
          {member.membership_reverted_from_name && (
            <p className="text-sm text-amber-600 dark:text-amber-500">
              {t("membership.revertedNotice", {
                plan: member.membership_reverted_from_name,
              })}
            </p>
          )}
        </CardContent>
      </Card>

      {/* An unpaid purchase grants nothing, so it is stated as money owed on a
          plan the member does not yet hold — never as the plan itself. */}
      {openPurchase && (
        <Card className="border-amber-500/50" data-testid="pending-purchase">
          <CardContent className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">{t("membership.awaitingPayment")}</Badge>
              <span className="font-medium">{planName(openPurchase.planId)}</span>
              <span className="font-mono text-sm">
                {formatCurrency(openPurchase.total)}
              </span>
            </div>
            <p className="text-sm text-muted-foreground">
              {t("membership.awaitingPaymentExplain", {
                receipt: openPurchase.receiptNumber,
                dueDate: formatDate(openPurchase.dueDate),
              })}
            </p>
            <div className="flex flex-wrap gap-2">
              {stripeActive && (
                <Button
                  size="sm"
                  onClick={() => handleStripe(openPurchase.receiptId)}
                  disabled={stripeCheckout.isPending}
                >
                  <CreditCard className="mr-2 h-4 w-4" />
                  {t("receipts.payNow")}
                </Button>
              )}
              {redsysActive && (
                <>
                  <RedsysPayButton receiptId={openPurchase.receiptId} method="card" />
                  <RedsysPayButton
                    receiptId={openPurchase.receiptId}
                    method="bizum"
                    variant="outline"
                  />
                </>
              )}
              {!stripeActive && !redsysActive && (
                <p className="text-sm text-muted-foreground">
                  {t("membership.noOnlinePayment")}
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      <h2 className="pt-2 text-lg font-semibold">{t("membership.availablePlans")}</h2>

      {plansLoading ? (
        <CardGridSkeleton cards={3} />
      ) : !purchasable.length ? (
        <div className="py-8 text-center text-muted-foreground">
          {t("membership.noPlans")}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="plan-catalogue">
          {purchasable.map((plan) => (
            <div
              key={plan.id}
              data-testid={`plan-card-${plan.slug}`}
              className="flex flex-col rounded-lg border p-4 transition-colors hover:bg-accent"
            >
              <p className="font-medium">{plan.name}</p>
              {plan.description && (
                <p className="mt-1 text-sm text-muted-foreground">{plan.description}</p>
              )}
              <p className="mt-3 font-mono text-lg">{formatCurrency(plan.base_price)}</p>
              <p className="text-xs text-muted-foreground">
                {t(`membership.frequency.${plan.billing_frequency}`)} ·{" "}
                {t("membership.beforeVat")}
              </p>
              <Button
                size="sm"
                className="mt-4 self-start"
                onClick={() => setSelected(plan)}
              >
                {t("membership.choosePlan")}
              </Button>
            </div>
          ))}
        </div>
      )}

      <PurchasePlanDialog
        plan={selected}
        onClose={() => setSelected(null)}
        onPurchased={(result) => {
          setJustPurchased(result);
          setSelected(null);
        }}
      />
    </div>
  );
}
