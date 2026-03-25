"use client";

import { use, useState } from "react";
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

export default function RegisterPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const activityId = Number(id);
  const t = useTranslations();
  const router = useRouter();

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

  if (actLoading || eligLoading) {
    return <FormSkeleton fields={3} />;
  }

  if (!activity) {
    return <div className="py-8 text-center text-muted-foreground">{t("common.notFound")}</div>;
  }

  const visiblePrices = activity.prices.filter((p) => p.is_visible && p.is_active);
  const hasModalities = activity.modalities.length > 0;
  const isAlreadyRegistered = eligibility?.reasons?.some((r) =>
    r.toLowerCase().includes("already registered")
  );

  const mandatoryConsents = activityConsents.filter((c: ActivityConsentData) => c.is_mandatory);
  const allMandatoryAccepted = mandatoryConsents.every((c: ActivityConsentData) => acceptedConsents[c.id]);

  async function handleValidateDiscount() {
    if (!discountCode.trim()) return;
    setDiscountChecking(true);
    try {
      const result = await validateDiscount(activityId, discountCode.trim(), selectedPriceId || undefined);
      setDiscountResult(result);
    } catch {
      setDiscountResult({ valid: false, error: "Failed to validate", discount_type: null, discount_value: null, original_amount: null, discounted_amount: null });
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
      await registerMutation.mutateAsync({
        activityId,
        price_id: selectedPriceId,
        modality_id: selectedModalityId || undefined,
        discount_code: discountResult?.valid ? discountCode.trim() : undefined,
        consents: consentsPayload.length > 0 ? consentsPayload : undefined,
        member_notes: notes || undefined,
      });
      toast.success(t("toast.success.created"));
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
              <Badge variant="default">{t("activities.registration.eligible")}</Badge>
              <span className="text-sm text-muted-foreground">
                {activity.available_spots > 0
                  ? t("activities.availableSpots", { count: activity.available_spots })
                  : t("activities.full")}
              </span>
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
                {eligibility?.reasons.map((r, i) => <li key={i}>{r}</li>)}
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
                      {p.name} — {p.amount > 0 ? `${Number(p.amount).toFixed(2)} EUR` : t("activities.prices.free")}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
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
                    ? `${discountResult.discount_type === "percentage" ? `${discountResult.discount_value}%` : `${Number(discountResult.discount_value).toFixed(2)} EUR`} ${t("activities.discounts.discountApplied")}${discountResult.discounted_amount != null ? ` — ${Number(discountResult.discounted_amount).toFixed(2)} EUR` : ""}`
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
            <div className="flex gap-3">
              <Button
                onClick={handleRegister}
                disabled={!selectedPriceId || !allMandatoryAccepted || registerMutation.isPending}
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
