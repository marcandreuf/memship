"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { useZodResolver } from "@/hooks/use-zod-resolver";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { toast } from "sonner";
import { mapApiErrorsToForm } from "@/lib/errors";
import { useOrgSettings, useUpdateSettings } from "../hooks/use-settings";
import { FormSkeleton } from "@/components/ui/skeletons";

const donationsSchema = z
  .object({
    member_donations_enabled: z.boolean(),
    donation_min_amount: z.coerce.number<number>().int().min(1).max(100000),
    donation_max_amount: z.coerce.number<number>().int().min(1).max(100000),
    donation_message: z.string().max(2000),
  })
  // The server refuses this pair too, but only when one request carries both
  // keys — which this form always does. Saying so here means the administrator
  // is told at the field rather than by a 422.
  .refine((data) => data.donation_max_amount >= data.donation_min_amount, {
    path: ["donation_max_amount"],
    message: "validation.maxLessThanMin",
  });

type DonationsFormValues = z.infer<typeof donationsSchema>;

/**
 * Whether members can donate, what they are asked, and the amounts accepted.
 *
 * The message is the only part of this that is not a number: a donation is not
 * a purchase, so the reason to give has to be the club's own words, in its own
 * language. Left empty, the donate page simply shows the amounts.
 *
 * The minimum does double duty: it is the floor the server enforces, and it is
 * what the suggested amounts are derived from (min × 1, 2, 5, 10), so the
 * description says so rather than leaving an administrator to notice.
 */
export function DonationsSettings() {
  const t = useTranslations();
  // The full record, not the branding subset: `donation_message` is a column
  // the shell has no business carrying, so only this form reads it.
  const { data: settings, isLoading } = useOrgSettings();
  const updateMutation = useUpdateSettings();

  const form = useForm<DonationsFormValues>({
    resolver: useZodResolver(donationsSchema),
    defaultValues: {
      member_donations_enabled: false,
      donation_min_amount: 5,
      donation_max_amount: 1000,
      donation_message: "",
    },
  });

  useEffect(() => {
    if (settings) {
      const features = settings.features ?? {};
      form.reset({
        member_donations_enabled: Boolean(features.member_donations_enabled),
        donation_min_amount: Number(features.donation_min_amount ?? 5),
        donation_max_amount: Number(features.donation_max_amount ?? 1000),
        donation_message: settings.donation_message ?? "",
      });
    }
  }, [settings, form]);

  if (isLoading) return <FormSkeleton fields={4} />;

  async function onSubmit(data: DonationsFormValues) {
    // `features` is a sparse update — send only the keys this form owns (#314).
    // `donation_message` is a column rather than a flag, so it sits beside it
    // in the same PUT. An empty box clears the ask without switching the
    // feature off, which is why it is sent as null rather than omitted.
    const payload = {
      donation_message: data.donation_message.trim() || null,
      features: {
        member_donations_enabled: data.member_donations_enabled,
        donation_min_amount: data.donation_min_amount,
        donation_max_amount: data.donation_max_amount,
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
              {t("settings.donations.title")}
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 sm:grid-cols-2 px-4 pb-3 pt-0">
            <FormField
              control={form.control}
              name="member_donations_enabled"
              render={({ field }) => (
                <FormItem className="flex items-center justify-between gap-2 rounded-lg border p-2.5 sm:col-span-2">
                  <div>
                    <FormLabel className="mt-0 text-xs">
                      {t("settings.donations.enabled")}
                    </FormLabel>
                    <FormDescription className="text-xs">
                      {t("settings.donations.enabledDesc")}
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
              name="donation_min_amount"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-xs">
                    {t("settings.donations.minAmount")}
                  </FormLabel>
                  <FormControl>
                    <Input
                      className="h-8"
                      type="number"
                      min={1}
                      max={100000}
                      {...field}
                    />
                  </FormControl>
                  <FormDescription className="text-xs">
                    {t("settings.donations.minAmountDesc")}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="donation_max_amount"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-xs">
                    {t("settings.donations.maxAmount")}
                  </FormLabel>
                  <FormControl>
                    <Input
                      className="h-8"
                      type="number"
                      min={1}
                      max={100000}
                      {...field}
                    />
                  </FormControl>
                  <FormDescription className="text-xs">
                    {t("settings.donations.maxAmountDesc")}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="donation_message"
              render={({ field }) => (
                <FormItem className="sm:col-span-2">
                  <FormLabel className="text-xs">
                    {t("settings.donations.message")}
                  </FormLabel>
                  <FormControl>
                    <Textarea rows={4} {...field} />
                  </FormControl>
                  <FormDescription className="text-xs">
                    {t("settings.donations.messageDesc")}
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
