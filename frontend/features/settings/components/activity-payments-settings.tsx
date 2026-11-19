"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { useZodResolver } from "@/hooks/use-zod-resolver";
import { z } from "zod";
import { AlertTriangle } from "lucide-react";
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
import { mapApiErrorsToForm } from "@/lib/errors";
import { usePermissions } from "@/features/auth/hooks/use-permissions";
import { usePaymentOptions } from "@/features/activities/hooks/use-activities";
import { useSettings, useUpdateSettings } from "../hooks/use-settings";

const DEFAULT_HOURS = 72;

const schema = z.object({
  activity_auto_cancel_enabled: z.boolean(),
  activity_auto_cancel_hours: z.coerce.number<number>().int().min(1).max(8760),
});

type Values = z.infer<typeof schema>;

/**
 * The club's default for releasing unpaid pay-to-confirm seats (#591). Each
 * activity may override it; one left on "As the club" follows this.
 */
export function ActivityPaymentsSettings() {
  const t = useTranslations();
  const { has } = usePermissions();
  const { data: settings, isLoading } = useSettings();
  const { data: options } = usePaymentOptions(true);
  const updateMutation = useUpdateSettings();

  const form = useForm<Values>({
    resolver: useZodResolver(schema),
    defaultValues: { activity_auto_cancel_enabled: false, activity_auto_cancel_hours: DEFAULT_HOURS },
  });

  useEffect(() => {
    if (settings) {
      const features = settings.features ?? {};
      form.reset({
        activity_auto_cancel_enabled: features.activity_auto_cancel_enabled === true,
        activity_auto_cancel_hours: Number(features.activity_auto_cancel_hours ?? DEFAULT_HOURS),
      });
    }
  }, [settings, form]);

  if (isLoading) return <FormSkeleton fields={2} />;

  const enabled = form.watch("activity_auto_cancel_enabled");
  const switchedOff = options?.switched_off_templates ?? [];
  const templateNames = switchedOff
    .map((key) => t(`settings.emailTemplates.templates.${key}.name`))
    .join(", ");
  const fixIt = has("settings.communications.write")
    ? t("activities.payment.fixInSettings", { count: switchedOff.length })
    : t("activities.payment.fixAskAdmin");

  async function onSubmit(data: Values) {
    // `features` is a sparse update: send only what this form owns (#314).
    try {
      await updateMutation.mutateAsync({ features: data });
      toast.success(t("toast.success.saved"));
    } catch (error) {
      mapApiErrorsToForm(error, form);
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-3 max-w-4xl">
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-base">{t("settings.activityPayments.title")}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 sm:grid-cols-2 px-4 pb-3 pt-0">
            <FormField
              control={form.control}
              name="activity_auto_cancel_enabled"
              render={({ field }) => (
                <FormItem className="flex items-center justify-between gap-2 rounded-lg border p-2.5 sm:col-span-2">
                  <div>
                    <FormLabel className="mt-0 text-xs">{t("settings.activityPayments.autoCancel")}</FormLabel>
                    <FormDescription className="text-xs">
                      {t("settings.activityPayments.autoCancelDesc")}
                    </FormDescription>
                  </div>
                  <FormControl>
                    <Switch checked={field.value} onCheckedChange={field.onChange} />
                  </FormControl>
                </FormItem>
              )}
            />
            {enabled && switchedOff.length > 0 && (
              <p className="sm:col-span-2 flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 p-2 text-xs text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                <span>
                  {t("activities.payment.autoCancelNeedsEmails", { templates: templateNames })} {fixIt}
                </span>
              </p>
            )}
            <FormField
              control={form.control}
              name="activity_auto_cancel_hours"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-xs">{t("settings.activityPayments.hours")}</FormLabel>
                  <FormControl>
                    <Input className="h-8" type="number" min={1} max={8760} {...field} />
                  </FormControl>
                  <FormDescription className="text-xs">
                    {t("settings.activityPayments.hoursDesc")}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        <Button type="submit" disabled={updateMutation.isPending}>
          {updateMutation.isPending ? t("common.loading") : t("common.save")}
        </Button>
      </form>
    </Form>
  );
}
