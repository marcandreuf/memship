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

const paymentRemindersSchema = z.object({
  payment_reminders_enabled: z.boolean(),
  reminder_days_after_due: z.coerce.number().int().min(0).max(365),
  reminder_repeat_days: z.coerce.number().int().min(1).max(365),
  reminder_max_count: z.coerce.number().int().min(1).max(10),
});

type PaymentRemindersFormValues = z.infer<typeof paymentRemindersSchema>;

export function PaymentRemindersSettings() {
  const t = useTranslations();
  const { data: settings, isLoading } = useSettings();
  const updateMutation = useUpdateSettings();

  const form = useForm<PaymentRemindersFormValues>({
    resolver: zodResolver(paymentRemindersSchema),
    defaultValues: {
      payment_reminders_enabled: false,
      reminder_days_after_due: 3,
      reminder_repeat_days: 7,
      reminder_max_count: 3,
    },
  });

  useEffect(() => {
    if (settings) {
      const features = settings.features ?? {};
      form.reset({
        payment_reminders_enabled:
          Boolean(features.payment_reminders_enabled) || false,
        reminder_days_after_due:
          Number(features.reminder_days_after_due ?? 3),
        reminder_repeat_days: Number(features.reminder_repeat_days ?? 7),
        reminder_max_count: Number(features.reminder_max_count ?? 3),
      });
    }
  }, [settings, form]);

  if (isLoading) return <FormSkeleton fields={4} />;

  async function onSubmit(data: PaymentRemindersFormValues) {
    // PUT /settings replaces the whole features JSONB dict — merge to keep
    // other feature flags (e.g. recurring_billing_enabled) intact.
    const payload = {
      features: {
        ...(settings?.features ?? {}),
        payment_reminders_enabled: data.payment_reminders_enabled,
        reminder_days_after_due: data.reminder_days_after_due,
        reminder_repeat_days: data.reminder_repeat_days,
        reminder_max_count: data.reminder_max_count,
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
              {t("settings.paymentReminders.title")}
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 sm:grid-cols-2 px-4 pb-3 pt-0">
            <FormField
              control={form.control}
              name="payment_reminders_enabled"
              render={({ field }) => (
                <FormItem className="flex items-center justify-between gap-2 rounded-lg border p-2.5 sm:col-span-2">
                  <div>
                    <FormLabel className="mt-0 text-xs">
                      {t("settings.paymentReminders.enabled")}
                    </FormLabel>
                    <FormDescription className="text-xs">
                      {t("settings.paymentReminders.enabledDesc")}
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
              name="reminder_days_after_due"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-xs">
                    {t("settings.paymentReminders.daysAfterDue")}
                  </FormLabel>
                  <FormControl>
                    <Input
                      className="h-8"
                      type="number"
                      min={0}
                      max={365}
                      {...field}
                    />
                  </FormControl>
                  <FormDescription className="text-xs">
                    {t("settings.paymentReminders.daysAfterDueDesc")}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="reminder_repeat_days"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-xs">
                    {t("settings.paymentReminders.repeatDays")}
                  </FormLabel>
                  <FormControl>
                    <Input
                      className="h-8"
                      type="number"
                      min={1}
                      max={365}
                      {...field}
                    />
                  </FormControl>
                  <FormDescription className="text-xs">
                    {t("settings.paymentReminders.repeatDaysDesc")}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="reminder_max_count"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-xs">
                    {t("settings.paymentReminders.maxCount")}
                  </FormLabel>
                  <FormControl>
                    <Input
                      className="h-8"
                      type="number"
                      min={1}
                      max={10}
                      {...field}
                    />
                  </FormControl>
                  <FormDescription className="text-xs">
                    {t("settings.paymentReminders.maxCountDesc")}
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
