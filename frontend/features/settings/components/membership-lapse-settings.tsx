"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { useZodResolver } from "@/hooks/use-zod-resolver";
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

const membershipLapseSchema = z.object({
  membership_lapse_enabled: z.boolean(),
  membership_fee_due_days: z.coerce.number().int().min(0).max(365),
  membership_lapse_grace_days: z.coerce.number().int().min(0).max(365),
});

type MembershipLapseFormValues = z.infer<typeof membershipLapseSchema>;

export function MembershipLapseSettings() {
  const t = useTranslations();
  const { data: settings, isLoading } = useSettings();
  const updateMutation = useUpdateSettings();

  const form = useForm<MembershipLapseFormValues>({
    resolver: useZodResolver(membershipLapseSchema),
    defaultValues: {
      membership_lapse_enabled: false,
      membership_fee_due_days: 7,
      membership_lapse_grace_days: 21,
    },
  });

  const enabled = form.watch("membership_lapse_enabled");
  const dueDays = Number(form.watch("membership_fee_due_days")) || 0;
  const graceDays = Number(form.watch("membership_lapse_grace_days")) || 0;
  // Reversion is deliberately independent of the reminder pipeline, so a club
  // can downgrade members it never chased. Say so where it is switched on.
  const remindersOff = !settings?.features?.payment_reminders_enabled;

  useEffect(() => {
    if (settings) {
      const features = settings.features ?? {};
      form.reset({
        membership_lapse_enabled:
          Boolean(features.membership_lapse_enabled) || false,
        membership_fee_due_days: Number(features.membership_fee_due_days ?? 7),
        membership_lapse_grace_days: Number(
          features.membership_lapse_grace_days ?? 21,
        ),
      });
    }
  }, [settings, form]);

  if (isLoading) return <FormSkeleton fields={3} />;

  async function onSubmit(data: MembershipLapseFormValues) {
    // PUT /settings replaces the whole features JSONB dict — merge to keep
    // other feature flags (e.g. recurring_billing_enabled) intact.
    const payload = {
      features: {
        ...(settings?.features ?? {}),
        membership_lapse_enabled: data.membership_lapse_enabled,
        membership_fee_due_days: data.membership_fee_due_days,
        membership_lapse_grace_days: data.membership_lapse_grace_days,
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
              {t("settings.membershipLapse.title")}
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 sm:grid-cols-2 px-4 pb-3 pt-0">
            <FormField
              control={form.control}
              name="membership_lapse_enabled"
              render={({ field }) => (
                <FormItem className="flex items-center justify-between gap-2 rounded-lg border p-2.5 sm:col-span-2">
                  <div>
                    <FormLabel className="mt-0 text-xs">
                      {t("settings.membershipLapse.enabled")}
                    </FormLabel>
                    <FormDescription className="text-xs">
                      {t("settings.membershipLapse.enabledDesc")}
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

            {enabled && remindersOff && (
              <div className="sm:col-span-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
                {t("settings.membershipLapse.noRemindersWarning")}
              </div>
            )}

            <FormField
              control={form.control}
              name="membership_fee_due_days"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-xs">
                    {t("settings.membershipLapse.dueDays")}
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
                    {t("settings.membershipLapse.dueDaysDesc")}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="membership_lapse_grace_days"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-xs">
                    {t("settings.membershipLapse.graceDays")}
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
                    {t("settings.membershipLapse.graceDaysDesc")}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <p className="sm:col-span-2 text-xs text-muted-foreground">
              {t("settings.membershipLapse.summary", {
                days: dueDays + graceDays,
              })}
            </p>
          </CardContent>
        </Card>

        <Button type="submit" disabled={updateMutation.isPending}>
          {updateMutation.isPending ? t("common.loading") : t("common.save")}
        </Button>
      </form>
    </Form>
  );
}
