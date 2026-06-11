"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  FormDescription,
} from "@/components/ui/form";
import { toast } from "sonner";
import { mapApiErrorsToForm } from "@/lib/errors";
import { useSettings, useUpdateSettings } from "../hooks/use-settings";
import { FormSkeleton } from "@/components/ui/skeletons";

const recurringBillingSchema = z.object({
  recurring_billing_enabled: z.boolean(),
  recurring_billing_day: z.coerce.number().int().min(1).max(28),
  billing_notification_email: z
    .string()
    .email()
    .max(255)
    .optional()
    .or(z.literal("")),
});

type RecurringBillingFormValues = z.infer<typeof recurringBillingSchema>;

export function RecurringBillingSettings() {
  const t = useTranslations();
  const { data: settings, isLoading } = useSettings();
  const updateMutation = useUpdateSettings();

  const form = useForm<RecurringBillingFormValues>({
    resolver: zodResolver(recurringBillingSchema),
    defaultValues: {
      recurring_billing_enabled: false,
      recurring_billing_day: 1,
      billing_notification_email: "",
    },
  });

  useEffect(() => {
    if (settings) {
      const features = settings.features ?? {};
      form.reset({
        recurring_billing_enabled:
          Boolean(features.recurring_billing_enabled) || false,
        recurring_billing_day:
          Number(features.recurring_billing_day) || 1,
        billing_notification_email:
          (features.billing_notification_email as string | null) || "",
      });
    }
  }, [settings, form]);

  if (isLoading) return <FormSkeleton fields={3} />;

  async function onSubmit(data: RecurringBillingFormValues) {
    // PUT /settings replaces the whole features JSONB dict — merge to keep
    // other feature flags (e.g. waiting_list) intact.
    const payload = {
      features: {
        ...(settings?.features ?? {}),
        recurring_billing_enabled: data.recurring_billing_enabled,
        recurring_billing_day: data.recurring_billing_day,
        billing_notification_email: data.billing_notification_email || null,
      },
    };
    try {
      await updateMutation.mutateAsync(payload);
      toast.success(t("toast.success.saved"));
    } catch (error) {
      mapApiErrorsToForm(error, form);
    }
  }

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onSubmit)}
        className="space-y-3 max-w-4xl"
      >
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-base">
              {t("settings.recurringBilling.title")}
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 sm:grid-cols-2 px-4 pb-3 pt-0">
            <FormField
              control={form.control}
              name="recurring_billing_enabled"
              render={({ field }) => (
                <FormItem className="flex items-center justify-between gap-2 rounded-lg border p-2.5 sm:col-span-2">
                  <div>
                    <FormLabel className="mt-0 text-xs">
                      {t("settings.recurringBilling.enabled")}
                    </FormLabel>
                    <FormDescription className="text-xs">
                      {t("settings.recurringBilling.enabledDesc")}
                    </FormDescription>
                  </div>
                  <FormControl>
                    <Switch
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  </FormControl>
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="recurring_billing_day"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-xs">
                    {t("settings.recurringBilling.day")}
                  </FormLabel>
                  <FormControl>
                    <Input
                      className="h-8"
                      type="number"
                      min={1}
                      max={28}
                      {...field}
                    />
                  </FormControl>
                  <FormDescription className="text-xs">
                    {t("settings.recurringBilling.dayDesc")}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="billing_notification_email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-xs">
                    {t("settings.recurringBilling.notificationEmail")}
                  </FormLabel>
                  <FormControl>
                    <Input
                      className="h-8"
                      type="email"
                      placeholder="admin@example.org"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription className="text-xs">
                    {t("settings.recurringBilling.notificationEmailDesc")}
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
