"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
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
import { toast } from "sonner";
import { mapApiErrorsToForm } from "@/lib/errors";
import { useOrgSettings, useUpdateSettings } from "../hooks/use-settings";
import { useAssignMemberNumbers } from "@/features/member-card/hooks/use-member-card";
import { FormSkeleton } from "@/components/ui/skeletons";

const memberCardSchema = z.object({
  member_card: z.boolean(),
  member_number_prefix: z.string().max(20),
  member_number_padding: z.coerce.number().int().min(1).max(10),
});

type MemberCardFormValues = z.infer<typeof memberCardSchema>;

export function MemberCardSettings() {
  const t = useTranslations();
  const { data: settings, isLoading } = useOrgSettings();
  const updateMutation = useUpdateSettings();
  const assignMutation = useAssignMemberNumbers();

  const form = useForm<MemberCardFormValues>({
    resolver: zodResolver(memberCardSchema),
    defaultValues: {
      member_card: false,
      member_number_prefix: "",
      member_number_padding: 4,
    },
  });

  useEffect(() => {
    if (settings) {
      const features = settings.features ?? {};
      form.reset({
        member_card: Boolean(features.member_card) || false,
        member_number_prefix: settings.member_number_prefix ?? "",
        member_number_padding: settings.member_number_padding ?? 4,
      });
    }
  }, [settings, form]);

  if (isLoading) return <FormSkeleton fields={3} />;

  async function onSubmit(data: MemberCardFormValues) {
    // PUT /settings replaces the whole features JSONB dict — merge to keep
    // sibling flags intact.
    const payload = {
      features: {
        ...(settings?.features ?? {}),
        member_card: data.member_card,
      },
      member_number_prefix: data.member_number_prefix,
      member_number_padding: data.member_number_padding,
    };
    try {
      await updateMutation.mutateAsync(payload);
      toast.success(t("toast.success.saved"));
    } catch (error) {
      mapApiErrorsToForm(error, form);
    }
  }

  async function onAssignNumbers() {
    try {
      const result = await assignMutation.mutateAsync();
      toast.success(t("settings.memberCard.assignedCount", { count: result.assigned }));
    } catch {
      toast.error(t("toast.error.generic"));
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-3 max-w-4xl">
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-base">{t("settings.memberCard.title")}</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-3 pt-0">
            <FormField
              control={form.control}
              name="member_card"
              render={({ field }) => (
                <FormItem className="flex items-center justify-between gap-2 rounded-lg border p-2.5">
                  <div>
                    <FormLabel className="mt-0 text-xs">
                      {t("settings.memberCard.enabled")}
                    </FormLabel>
                    <FormDescription className="text-xs">
                      {t("settings.memberCard.enabledDesc")}
                    </FormDescription>
                  </div>
                  <FormControl>
                    <Switch checked={field.value} onCheckedChange={field.onChange} />
                  </FormControl>
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-base">
              {t("settings.memberCard.numberingTitle")}
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 sm:grid-cols-2 px-4 pb-3 pt-0">
            <FormField
              control={form.control}
              name="member_number_prefix"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-xs">
                    {t("settings.memberCard.prefix")}
                  </FormLabel>
                  <FormControl>
                    <Input className="h-8" placeholder="SCB-" {...field} />
                  </FormControl>
                  <FormDescription className="text-xs">
                    {t("settings.memberCard.prefixHint")}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="member_number_padding"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-xs">
                    {t("settings.memberCard.padding")}
                  </FormLabel>
                  <FormControl>
                    <Input className="h-8" type="number" min={1} max={10} {...field} />
                  </FormControl>
                  <FormDescription className="text-xs">
                    {t("settings.memberCard.paddingHint")}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        <div className="flex items-center gap-3">
          <Button type="submit" disabled={updateMutation.isPending}>
            {updateMutation.isPending ? t("common.loading") : t("common.save")}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={onAssignNumbers}
            disabled={assignMutation.isPending}
          >
            {assignMutation.isPending
              ? t("common.loading")
              : t("settings.memberCard.assignNumbers")}
          </Button>
        </div>
      </form>
    </Form>
  );
}
