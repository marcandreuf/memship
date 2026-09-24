"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FormSkeleton } from "@/components/ui/skeletons";
import { useSettings, useUpdateSettings } from "../hooks/use-settings";

// Mirrors backend `app/domains/bookings/rules.py`.
const WINDOW_DAYS = { min: 1, max: 365 };
const DEADLINE_HOURS = { min: 0, max: 8760 };

function parseRule(value: string, { min, max }: { min: number; max: number }) {
  if (!/^\d+$/.test(value.trim())) return null;
  const n = Number(value);
  return n >= min && n <= max ? n : null;
}

export function BookingsSettings() {
  const t = useTranslations();
  const { data: settings, isLoading } = useSettings();
  const updateSettings = useUpdateSettings();

  const features = settings?.features ?? {};
  const enabled = Boolean(features.bookings);
  const waitlist = features.booking_waitlist_enabled !== false; // default true

  const [windowDays, setWindowDays] = useState<string>(
    String(features.booking_window_days ?? 14)
  );
  const [deadlineHours, setDeadlineHours] = useState<string>(
    String(features.booking_cancellation_deadline_hours ?? 24)
  );

  const [windowError, setWindowError] = useState(false);
  const [deadlineError, setDeadlineError] = useState(false);

  if (isLoading) return <FormSkeleton fields={2} />;

  async function save(partial: Record<string, unknown>) {
    try {
      await updateSettings.mutateAsync({
        features: { ...(settings?.features ?? {}), ...partial },
      });
      toast.success(t("toast.success.saved"));
    } catch {
      /* global handler shows the error toast */
    }
  }

  return (
    <div className="space-y-3 max-w-4xl">
      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-base">{t("bookings.settings.title")}</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-3 pt-0">
          <div className="flex items-center justify-between gap-2 rounded-lg border p-2.5">
            <div>
              <p className="text-xs font-medium">
                {t("bookings.settings.enabled")}
              </p>
              <p className="text-xs text-muted-foreground">
                {t("bookings.settings.enabledDesc")}
              </p>
            </div>
            <Switch
              checked={enabled}
              onCheckedChange={(checked) => save({ bookings: checked })}
              disabled={updateSettings.isPending}
            />
          </div>
        </CardContent>
      </Card>

      {enabled && (
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-base">
              {t("bookings.settings.rules")}
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-3 pt-0 space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label className="text-xs">
                  {t("bookings.settings.windowDays")}
                </Label>
                <Input
                  className="h-8"
                  type="number"
                  min={WINDOW_DAYS.min}
                  max={WINDOW_DAYS.max}
                  value={windowDays}
                  aria-invalid={windowError}
                  onChange={(e) => setWindowDays(e.target.value)}
                  onBlur={() => {
                    const n = parseRule(windowDays, WINDOW_DAYS);
                    setWindowError(n === null);
                    if (n !== null && n !== features.booking_window_days)
                      save({ booking_window_days: n });
                  }}
                />
                {windowError && (
                  <p className="text-xs text-destructive">
                    {t("bookings.settings.invalidNumber", WINDOW_DAYS)}
                  </p>
                )}
              </div>
              <div className="space-y-1">
                <Label className="text-xs">
                  {t("bookings.settings.deadlineHours")}
                </Label>
                <Input
                  className="h-8"
                  type="number"
                  min={DEADLINE_HOURS.min}
                  max={DEADLINE_HOURS.max}
                  value={deadlineHours}
                  aria-invalid={deadlineError}
                  onChange={(e) => setDeadlineHours(e.target.value)}
                  onBlur={() => {
                    const n = parseRule(deadlineHours, DEADLINE_HOURS);
                    setDeadlineError(n === null);
                    if (
                      n !== null &&
                      n !== features.booking_cancellation_deadline_hours
                    )
                      save({ booking_cancellation_deadline_hours: n });
                  }}
                />
                {deadlineError && (
                  <p className="text-xs text-destructive">
                    {t("bookings.settings.invalidNumber", DEADLINE_HOURS)}
                  </p>
                )}
              </div>
            </div>

            <div className="flex items-center justify-between gap-2 rounded-lg border p-2.5">
              <div>
                <p className="text-xs font-medium">
                  {t("bookings.settings.waitlist")}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t("bookings.settings.waitlistDesc")}
                </p>
              </div>
              <Switch
                checked={waitlist}
                onCheckedChange={(checked) =>
                  save({ booking_waitlist_enabled: checked })
                }
                disabled={updateSettings.isPending}
              />
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
