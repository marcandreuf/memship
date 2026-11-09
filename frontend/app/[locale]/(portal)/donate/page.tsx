"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { HandCoins, CreditCard } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageInfo } from "@/components/page-info";
import { FormSkeleton } from "@/components/ui/skeletons";
import { useFormatters } from "@/hooks/use-formatters";
import { useAuth } from "@/features/auth/hooks/use-auth";
import {
  useCreateDonation,
  useDonationOptions,
} from "@/features/donations/hooks/use-donations";
import type { DonationResult } from "@/features/donations/services/donations-api";
import { RedsysPayButton } from "@/features/receipts/components/redsys-pay-button";
import { useStripeCheckout } from "@/features/receipts/hooks/use-receipts";
import { useActivePaymentMethods } from "@/features/settings/hooks/use-payment-providers";

/**
 * A member giving the organisation money beyond their fee.
 *
 * A page rather than a dialog, because a donation is not a purchase: the
 * reason to give has to come from the organisation in its own words, and that
 * is `options.message`. The amount is picked from a ladder the server derives
 * from the configured minimum, or typed into the free field.
 *
 * Raising the donation and paying it are two steps on purpose, exactly as
 * buying a plan is. The receipt exists the moment the member confirms, and the
 * payment buttons that appear are the same ones `/my-receipts` uses, hitting
 * the same gateway the club already collects fees through. A donation nobody
 * pays is voided on its due date and never chased.
 *
 * Deliberately no direct-debit button. The mandate was signed for recurring
 * fees, and the receipt is raised unbatchable, so offering it here would be
 * offering something the server refuses to collect.
 */
export default function DonatePage() {
  const t = useTranslations();
  const { user } = useAuth();
  const { formatCurrency } = useFormatters();
  const { data: options, isLoading, isError } = useDonationOptions();
  const createDonation = useCreateDonation();

  const [amount, setAmount] = useState<string>("");
  const [raised, setRaised] = useState<DonationResult | null>(null);

  const stripeCheckout = useStripeCheckout();
  const { data: activeMethods } = useActivePaymentMethods();
  const activeTypes = new Set((activeMethods || []).map((m) => m.provider_type));
  const stripeActive = activeTypes.has("stripe");
  const redsysActive = activeTypes.has("redsys");
  // Bizum is a method of the Redsys provider, not a provider of its own, and
  // the bank enables it per terminal (#405).
  const bizumActive = (activeMethods || []).some(
    (m) => m.provider_type === "redsys" && m.methods?.includes("bizum")
  );
  const noGateway = !stripeActive && !redsysActive && !bizumActive;

  const isMember = user?.member_id != null;
  const parsed = Number(amount.replace(",", "."));
  const inRange =
    options != null &&
    Number.isFinite(parsed) &&
    parsed >= options.min_amount &&
    parsed <= options.max_amount;

  async function handleConfirm() {
    if (!inRange) return;
    try {
      const result = await createDonation.mutateAsync(parsed);
      setRaised(result);
      toast.success(t("donations.raised"));
    } catch {
      /* global handler shows the error toast */
    }
  }

  async function handleStripe(receiptId: number) {
    try {
      const result = await stripeCheckout.mutateAsync(receiptId);
      window.location.href = result.redirect_url;
    } catch {
      /* global handler */
    }
  }

  if (!isMember) {
    return (
      <div className="space-y-3">
        <h1 className="text-2xl font-bold">{t("donations.title")}</h1>
        <div className="py-8 text-center text-muted-foreground">
          {t("donations.notAMember")}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <HandCoins className="h-6 w-6" />
          {t("donations.title")}
        </h1>
        <PageInfo text={t("donations.info")} />
      </div>

      {isLoading ? (
        <FormSkeleton fields={3} />
      ) : isError || !options ? (
        /* The options endpoint answers 404 when the club does not take
           donations, which is the same state as the page not existing. */
        <p className="py-8 text-center text-muted-foreground">
          {t("donations.unavailable")}
        </p>
      ) : (
        <>
          {options.message && (
            <Card>
              <CardContent>
                <p className="whitespace-pre-line text-sm">{options.message}</p>
              </CardContent>
            </Card>
          )}

          {/* The raised donation, waiting to be paid. Stated as a receipt the
              member can still walk away from, because that is what it is. */}
          {raised ? (
            <Card className="border-amber-500/50" data-testid="pending-donation">
              <CardContent className="space-y-3">
                <p className="font-medium">
                  {t("donations.awaitingPayment", {
                    amount: formatCurrency(raised.total_amount),
                  })}
                </p>
                <p className="text-sm text-muted-foreground">
                  {t("donations.awaitingPaymentExplain", {
                    receipt: raised.receipt_number,
                  })}
                </p>
                {noGateway ? (
                  <p className="text-sm text-muted-foreground">
                    {t("donations.noGateway")}
                  </p>
                ) : (
                  <div className="flex flex-wrap items-center gap-2">
                    {stripeActive && (
                      <Button
                        onClick={() => handleStripe(raised.receipt_id)}
                        disabled={stripeCheckout.isPending}
                      >
                        <CreditCard className="mr-2 h-4 w-4" />
                        {t("receipts.payNow")}
                      </Button>
                    )}
                    {redsysActive && (
                      <RedsysPayButton receiptId={raised.receipt_id} method="card" />
                    )}
                    {bizumActive && (
                      <RedsysPayButton
                        receiptId={raised.receipt_id}
                        method="bizum"
                        variant="outline"
                      />
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>{t("donations.chooseAmount")}</Label>
                  <div className="flex flex-wrap gap-2">
                    {options.suggested_amounts.map((suggested) => (
                      <Button
                        key={suggested}
                        type="button"
                        variant={parsed === suggested ? "default" : "outline"}
                        onClick={() => setAmount(String(suggested))}
                      >
                        {formatCurrency(suggested)}
                      </Button>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="donation-amount">
                    {t("donations.otherAmount")}
                  </Label>
                  <Input
                    id="donation-amount"
                    type="number"
                    inputMode="decimal"
                    step="0.01"
                    min={options.min_amount}
                    max={options.max_amount}
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    className="max-w-40"
                  />
                  {/* The same bounds the server enforces, so the member is told
                      here instead of by a refusal. */}
                  <p className="text-xs text-muted-foreground">
                    {t("donations.bounds", {
                      min: formatCurrency(options.min_amount),
                      max: formatCurrency(options.max_amount),
                    })}
                  </p>
                </div>

                <Button
                  onClick={handleConfirm}
                  disabled={!inRange || createDonation.isPending}
                >
                  {createDonation.isPending
                    ? t("common.loading")
                    : t("donations.confirm")}
                </Button>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
