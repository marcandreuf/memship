"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { useZodResolver } from "@/hooks/use-zod-resolver";
import { z } from "zod";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { FormSkeleton } from "@/components/ui/skeletons";
import { getErrorMessage, mapApiErrorsToForm } from "@/lib/errors";
import { useSettings, useUpdateSettings } from "../hooks/use-settings";

// The backend's defaults (bookings/rules.py), shown until the club sets its own.
const DEFAULTS = {
  booking_auto_cancel_enabled: false,
  booking_auto_cancel_hours: 24,
  booking_payment_cutoff_minutes: 60,
  booking_min_hold_minutes: 15,
  booking_auto_promotion_min_minutes: 120,
};

const minutes = (min: number, max: number) => z.coerce.number<number>().int().min(min).max(max);

const schema = z.object({
  booking_auto_cancel_enabled: z.boolean(),
  booking_auto_cancel_hours: minutes(1, 8760),
  booking_payment_cutoff_minutes: minutes(0, 10080),
  booking_min_hold_minutes: minutes(1, 1440),
  booking_auto_promotion_min_minutes: minutes(1, 10080),
});

type Values = z.infer<typeof schema>;
type NumberKey = Exclude<keyof Values, "booking_auto_cancel_enabled">;

/**
 * When a pay-to-confirm space's bookings must be paid (#603). Separate from the
 * activity values on purpose: a court slot and an event are not paid on the
 * same clock. Shown only where the bookings module is on.
 */
export function SpacePaymentsSettings() {
  const t = useTranslations();
  const { data: settings, isLoading } = useSettings();
  const updateMutation = useUpdateSettings();

  const form = useForm<Values>({
    resolver: useZodResolver(schema),
    defaultValues: DEFAULTS,
  });

  useEffect(() => {
    if (settings) {
      const features = settings.features ?? {};
      form.reset({
        booking_auto_cancel_enabled: features.booking_auto_cancel_enabled === true,
        booking_auto_cancel_hours: Number(features.booking_auto_cancel_hours ?? DEFAULTS.booking_auto_cancel_hours),
        booking_payment_cutoff_minutes: Number(
          features.booking_payment_cutoff_minutes ?? DEFAULTS.booking_payment_cutoff_minutes
        ),
        booking_min_hold_minutes: Number(features.booking_min_hold_minutes ?? DEFAULTS.booking_min_hold_minutes),
        booking_auto_promotion_min_minutes: Number(
          features.booking_auto_promotion_min_minutes ?? DEFAULTS.booking_auto_promotion_min_minutes
        ),
      });
    }
  }, [settings, form]);

  if (isLoading) return <FormSkeleton fields={4} />;
  if (!settings?.features?.bookings) return null;

  const enabled = form.watch("booking_auto_cancel_enabled");

  async function onSubmit(data: Values) {
    // `features` is a sparse update: send only what this form owns (#314).
    try {
      await updateMutation.mutateAsync({ features: data });
      toast.success(t("toast.success.saved"));
    } catch (error) {
      if (!mapApiErrorsToForm(error, form)) toast.error(getErrorMessage(error, t));
    }
  }

  const numberField = (name: NumberKey, max: number, min = 1) => (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormLabel className="text-xs">{t(`settings.spacePayments.${name}`)}</FormLabel>
          <FormControl>
            <Input className="h-8" type="number" min={min} max={max} {...field} />
          </FormControl>
          <FormDescription className="text-xs">
            {t(`settings.spacePayments.${name}Desc`)}
          </FormDescription>
          <FormMessage />
        </FormItem>
      )}
    />
  );

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-3 max-w-4xl">
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-base">{t("settings.spacePayments.title")}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 sm:grid-cols-2 px-4 pb-3 pt-0">
            <p className="sm:col-span-2 text-xs text-muted-foreground">
              {t("settings.spacePayments.intro")}
            </p>
            {numberField("booking_payment_cutoff_minutes", 10080, 0)}
            {numberField("booking_min_hold_minutes", 1440)}
            {numberField("booking_auto_promotion_min_minutes", 10080)}
            <FormField
              control={form.control}
              name="booking_auto_cancel_enabled"
              render={({ field }) => (
                <FormItem className="flex items-center justify-between gap-2 rounded-lg border p-2.5 sm:col-span-2">
                  <div>
                    <FormLabel className="mt-0 text-xs">{t("settings.spacePayments.autoCancel")}</FormLabel>
                    <FormDescription className="text-xs">
                      {t("settings.spacePayments.autoCancelDesc")}
                    </FormDescription>
                  </div>
                  <FormControl>
                    <Switch checked={field.value} onCheckedChange={field.onChange} />
                  </FormControl>
                </FormItem>
              )}
            />
            {enabled && numberField("booking_auto_cancel_hours", 8760)}
          </CardContent>
        </Card>

        <Button type="submit" disabled={updateMutation.isPending}>
          {updateMutation.isPending ? t("common.loading") : t("common.save")}
        </Button>
      </form>
    </Form>
  );
}
