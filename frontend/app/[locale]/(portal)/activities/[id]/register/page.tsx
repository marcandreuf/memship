"use client";

import { use, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/lib/i18n/routing";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { DetailHeader } from "@/components/entity/detail-header";
import { Link } from "@/lib/i18n/routing";
import { useActivity, useConsents } from "@/features/activities/hooks/use-activities";
import { validateDiscount } from "@/features/activities/services/activities-api";
import type { ValidateDiscountResult, ActivityConsentData } from "@/features/activities/services/activities-api";
import { useEligibility, useRegister } from "@/features/activities/hooks/use-registrations";
import { Checkbox } from "@/components/ui/checkbox";
import { FormSkeleton } from "@/components/ui/skeletons";
import { describeActivityTerms } from "@/features/activities/components/cancellation-policy-fields";
import { useFormatters } from "@/hooks/use-formatters";

export default function RegisterPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const activityId = Number(id);
  const t = useTranslations();
  const router = useRouter();
  const { formatCurrency } = useFormatters();

  const { data: activity, isLoading: actLoading } = useActivity(activityId);
  const { data: eligibility, isLoading: eligLoading } = useEligibility(activityId);
  const registerMutation = useRegister();

  const { data: activityConsents = [] } = useConsents(activityId);

  const [selectedPriceId, setSelectedPriceId] = useState<number | null>(null);
  const [selectedModalityId, setSelectedModalityId] = useState<number | null>(null);
  const [notes, setNotes] = useState("");
  const [discountCode, setDiscountCode] = useState("");
  const [discountResult, setDiscountResult] = useState<ValidateDiscountResult | null>(null);
  const [discountChecking, setDiscountChecking] = useState(false);
  const [acceptedConsents, setAcceptedConsents] = useState<Record<number, boolean>>({});

  // Preselect the price marked default. That is what the flag means, and until
  // #601 it meant nothing: it was stored and displayed and read by nobody, so
  // this page preselected nothing however an activity was configured. At most
  // one price per activity can carry it (uq_activity_prices_is_default), so
  // there is nothing to disambiguate. Initial value only: a member who picks
  // another price keeps their choice.
  useEffect(() => {
    if (selectedPriceId !== null) return;
    const preselect = activity?.prices.find(
      (p) => p.is_visible && p.is_active && p.is_default,
    );
    if (preselect) setSelectedPriceId(preselect.id);
  }, [activity, selectedPriceId]);

  if (actLoading || eligLoading) {
    return <FormSkeleton fields={3} />;
  }

  if (!activity) {
    return <div className="py-8 text-center text-muted-foreground">{t("common.notFound")}</div>;
  }

  const visiblePrices = activity.prices.filter((p) => p.is_visible && p.is_active);
  const selectedPrice = visiblePrices.find((p) => p.id === selectedPriceId);
  const hasModalities = activity.modalities.length > 0;
  const isAlreadyRegistered = eligibility?.details?.some((d) => d.code === "already_registered");

  const mandatoryConsents = activityConsents.filter((c: ActivityConsentData) => c.is_mandatory);
  const allMandatoryAccepted = mandatoryConsents.every((c: ActivityConsentData) => acceptedConsents[c.id]);
  // Only the activity-wide cap is known here; a full modality is still refused by the API.
  const isFull = activity.available_spots <= 0;
  const fullWithoutWaitlist = isFull && !activity.features?.waiting_list;

  async function handleValidateDiscount() {
    if (!discountCode.trim()) return;
    setDiscountChecking(true);
    try {
      const result = await validateDiscount(activityId, discountCode.trim(), selectedPriceId || undefined);
      setDiscountResult(result);
    } catch {
      setDiscountResult({ valid: false, error: t("activities.discounts.validationFailed"), discount_type: null, discount_value: null, original_amount: null, discounted_amount: null, original_total: null, discounted_total: null });
    }
    setDiscountChecking(false);
  }

  async function handleRegister() {
    if (!selectedPriceId) return;
    const consentsPayload = activityConsents.map((c: ActivityConsentData) => ({
      activity_consent_id: c.id,
      accepted: !!acceptedConsents[c.id],
    }));
    try {
      const registration = await registerMutation.mutateAsync({
        activityId,
        price_id: selectedPriceId,
        modality_id: selectedModalityId || undefined,
        discount_code: discountResult?.valid ? discountCode.trim() : undefined,
        consents: consentsPayload.length > 0 ? consentsPayload : undefined,
        member_notes: notes || undefined,
      });
      // The activity page then shows the held seat with its "Pay now".
      toast.success(
        registration.status === "pending"
          ? t("activities.registration.pendingCreated")
          : registration.status === "waitlist"
            ? t("activities.registration.waitlistCreated")
            : t("activities.registration.confirmedCreated"),
      );
      router.push(`/activities/${activityId}`);
    } catch { /* global handler shows error toast */ }
  }

  return (
    <div className="space-y-4">
      <DetailHeader
        breadcrumbs={[
          { label: t("activities.title"), href: "/activities" },
          { label: activity.name, href: `/activities/${activityId}` },
          { label: t("activities.registration.register") },
        ]}
        title={t("activities.registration.register")}
      />

      {/* Eligibility */}
      <Card>
        <CardContent className="py-3 px-4">
          {eligibility?.eligible ? (
            <div className="flex items-center gap-2">
              <Badge variant={isFull ? "outline" : "default"}>
                {t(
                  fullWithoutWaitlist
                    ? "activities.full"
                    : isFull
                      ? "activities.registration.eligibleWaitlist"
                      : "activities.registration.eligible"
                )}
              </Badge>
              {!fullWithoutWaitlist && (
                <span className="text-sm text-muted-foreground">
                  {isFull
                    ? t("activities.full")
                    : t("activities.availableSpots", { count: activity.available_spots })}
                </span>
              )}
            </div>
          ) : isAlreadyRegistered ? (
            <div className="flex items-center gap-3">
              <Badge variant="secondary">{t("activities.registration.registered")}</Badge>
              <span className="text-sm text-muted-foreground">
                {t("activities.registration.alreadyRegistered")}
              </span>
              <Link href="/my-activities">
                <Button variant="outline" size="sm">
                  {t("activities.registration.viewMyActivities")}
                </Button>
              </Link>
            </div>
          ) : (
            <div>
              <Badge variant="destructive">{t("activities.registration.notEligible")}</Badge>
              <ul className="mt-2 text-sm text-muted-foreground list-disc list-inside">
                {eligibility?.details.map((d, i) => {
                  const key = `activities.eligibility.${d.code}`;
                  // A code this build has no text for falls back to the API's own words.
                  return (
                    <li key={i}>
                      {t.has(key)
                        ? t(key, { min_age: d.min_age ?? 0, max_age: d.max_age ?? 0 })
                        : eligibility.reasons[i]}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      {eligibility?.eligible && (
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-base">{activity.name}</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 pt-0 space-y-4">
            {/* Modality selection */}
            {hasModalities && (
              <div>
                <p className="text-xs text-muted-foreground mb-1.5">
                  {t("activities.registration.selectModality")}
                </p>
                <Select
                  value={selectedModalityId?.toString() || ""}
                  onValueChange={(v) => setSelectedModalityId(v ? Number(v) : null)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t("activities.registration.selectModality")} />
                  </SelectTrigger>
                  <SelectContent>
                    {activity.modalities
                      .filter((m) => m.is_active)
                      .map((m) => (
                        <SelectItem key={m.id} value={m.id.toString()}>
                          {m.name}
                          {m.max_participants && (
                            <span className="text-muted-foreground ml-1">
                              ({m.current_participants}/{m.max_participants})
                            </span>
                          )}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* Price selection */}
            <div>
              <p className="text-xs text-muted-foreground mb-1.5">
                {t("activities.registration.selectPrice")}
              </p>
              <Select
                value={selectedPriceId?.toString() || ""}
                onValueChange={(v) => setSelectedPriceId(Number(v))}
              >
                <SelectTrigger>
                  <SelectValue placeholder={t("activities.registration.selectPrice")} />
                </SelectTrigger>
                <SelectContent>
                  {visiblePrices.map((p) => (
                    <SelectItem key={p.id} value={p.id.toString()}>
                      {p.name} — {p.amount > 0 ? formatCurrency(p.total_amount) : t("activities.prices.free")}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedPrice && selectedPrice.amount > 0 && selectedPrice.vat_amount > 0 && (
                // The figure above is tax-inclusive; show what it is made of so
                // it reconciles with the invoice rather than merely matching it.
                <p className="text-xs text-muted-foreground mt-1.5">
                  {t("activities.prices.vatBreakdown", {
                    base: formatCurrency(selectedPrice.amount),
                    rate: selectedPrice.vat_rate,
                    vat: formatCurrency(selectedPrice.vat_amount),
                  })}
                </p>
              )}
              {activity.payment_flow === "pay_to_confirm" && selectedPrice && selectedPrice.amount > 0 && !fullWithoutWaitlist && (
                // Said before signing up, not discovered after: the seat is
                // only held until the receipt is paid (#591).
                <p className="text-sm mt-2 rounded-md border border-amber-300 bg-amber-50 p-2 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
                  {isFull
                    ? t("activities.registration.heldAfterWaitlist")
                    : activity.auto_cancel_enabled && activity.auto_cancel_hours
                      ? t("activities.registration.heldUntilPaidWithin", { hours: activity.auto_cancel_hours })
                      : t("activities.registration.heldUntilPaid")}
                </p>
              )}
              {selectedPrice && selectedPrice.amount > 0 && (
                <p className="text-sm mt-2 text-muted-foreground" data-testid="cancellation-terms">
                  {t("activities.cancellationRule.deadline")}: {describeActivityTerms(t, activity)}
                </p>
              )}
            </div>

            {/* Discount code */}
            <div>
              <p className="text-xs text-muted-foreground mb-1.5">
                {t("activities.discounts.code")} ({t("activities.consents.optional").toLowerCase()})
              </p>
              <div className="flex gap-2">
                <Input
                  value={discountCode}
                  onChange={(e) => { setDiscountCode(e.target.value); setDiscountResult(null); }}
                  placeholder={t("activities.discounts.enterCode")}
                  className="uppercase"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleValidateDiscount}
                  disabled={!discountCode.trim() || discountChecking}
                >
                  {discountChecking ? t("common.loading") : t("activities.discounts.apply")}
                </Button>
              </div>
              {discountResult && (
                <p className={`text-sm mt-1 ${discountResult.valid ? "text-green-600" : "text-destructive"}`}>
                  {discountResult.valid
                    ? `${discountResult.discount_type === "percentage" ? `${discountResult.discount_value}%` : formatCurrency(discountResult.discount_value ?? 0)} ${t("activities.discounts.discountApplied")}${discountResult.discounted_total != null ? ` — ${formatCurrency(discountResult.discounted_total)}` : ""}`
                    : discountResult.error}
                </p>
              )}
            </div>

            {/* Consents */}
            {activityConsents.length > 0 && (
              <div className="space-y-3">
                <p className="text-xs text-muted-foreground">{t("activities.consents.title")}</p>
                {activityConsents.map((c: ActivityConsentData) => (
                  <div key={c.id} className="flex items-start gap-2">
                    <Checkbox
                      checked={!!acceptedConsents[c.id]}
                      onCheckedChange={(checked) =>
                        setAcceptedConsents((prev) => ({ ...prev, [c.id]: !!checked }))
                      }
                    />
                    <div className="text-sm">
                      <span className="font-medium">{c.title}</span>
                      {c.is_mandatory && <span className="text-destructive ml-1">*</span>}
                      <p className="text-muted-foreground text-xs mt-0.5">{c.content}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Notes */}
            <div>
              <p className="text-xs text-muted-foreground mb-1.5">
                {t("activities.registration.notes")}
              </p>
              <Textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={2}
              />
            </div>

            {/* Submit */}
            {fullWithoutWaitlist && (
              <p className="text-sm text-muted-foreground">
                {t("activities.registration.fullNoWaitlist")}
              </p>
            )}
            <div className="flex gap-3">
              <Button
                onClick={handleRegister}
                disabled={
                  !selectedPriceId ||
                  !allMandatoryAccepted ||
                  fullWithoutWaitlist ||
                  registerMutation.isPending
                }
              >
                {registerMutation.isPending
                  ? t("common.loading")
                  : t("activities.registration.register")}
              </Button>
              <Button
                variant="outline"
                onClick={() => router.push(`/activities/${activityId}`)}
              >
                {t("common.cancel")}
              </Button>
            </div>

          </CardContent>
        </Card>
      )}
    </div>
  );
}
