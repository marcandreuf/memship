"use client";

import { use, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/lib/i18n/routing";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DetailHeader } from "@/components/entity/detail-header";
import { Link } from "@/lib/i18n/routing";
import { useActivity } from "@/features/activities/hooks/use-activities";
import { useEligibility, useRegister } from "@/features/activities/hooks/use-registrations";

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

  const [selectedPriceId, setSelectedPriceId] = useState<number | null>(null);
  const [selectedModalityId, setSelectedModalityId] = useState<number | null>(null);
  const [notes, setNotes] = useState("");

  if (actLoading || eligLoading) {
    return <div className="py-8 text-center text-muted-foreground">{t("common.loading")}</div>;
  }

  if (!activity) {
    return <div className="py-8 text-center text-muted-foreground">{t("common.notFound")}</div>;
  }

  const visiblePrices = activity.prices.filter((p) => p.is_visible && p.is_active);
  const hasModalities = activity.modalities.length > 0;
  const isAlreadyRegistered = eligibility?.reasons?.some((r) =>
    r.toLowerCase().includes("already registered")
  );

  async function handleRegister() {
    if (!selectedPriceId) return;
    await registerMutation.mutateAsync({
      activityId,
      price_id: selectedPriceId,
      modality_id: selectedModalityId || undefined,
      member_notes: notes || undefined,
    });
    router.push(`/activities/${activityId}`);
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
                disabled={!selectedPriceId || registerMutation.isPending}
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

            {registerMutation.isError && (
              <p className="text-sm text-destructive">
                {(registerMutation.error as Error)?.message || "Registration failed"}
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
