"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  Card,
  CardContent,
  CardDescription,
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
} from "@/components/ui/form";
import { toast } from "sonner";
import { mapApiErrorsToForm } from "@/lib/errors";
import { useSettings, useUpdateSettings } from "../hooks/use-settings";
import { FormSkeleton } from "@/components/ui/skeletons";

const communicationsSchema = z.object({
  communications: z.boolean(),
});

type CommunicationsFormValues = z.infer<typeof communicationsSchema>;

export function CommunicationsSettings() {
  const t = useTranslations();
  const { data: settings, isLoading } = useSettings();
  const updateMutation = useUpdateSettings();

  const form = useForm<CommunicationsFormValues>({
    resolver: zodResolver(communicationsSchema),
    defaultValues: { communications: false },
  });

  useEffect(() => {
    if (settings) {
      const features = settings.features ?? {};
      form.reset({ communications: Boolean(features.communications) || false });
    }
  }, [settings, form]);

  if (isLoading) return <FormSkeleton fields={1} />;

  async function onSubmit(data: CommunicationsFormValues) {
    // PUT /settings replaces the whole features JSONB dict — merge to keep
    // sibling flags intact.
    const payload = {
      features: {
        ...(settings?.features ?? {}),
        communications: data.communications,
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
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-3 max-w-4xl">
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-base">
              {t("settings.communications.title")}
            </CardTitle>
            <CardDescription className="text-xs">
              {t("settings.communications.description")}
            </CardDescription>
          </CardHeader>
          <CardContent className="px-4 pb-3 pt-0">
            <FormField
              control={form.control}
              name="communications"
              render={({ field }) => (
                <FormItem className="flex items-center justify-between gap-2 rounded-lg border p-2.5">
                  <div>
                    <FormLabel className="mt-0 text-xs">
                      {t("settings.communications.enabled")}
                    </FormLabel>
                    <FormDescription className="text-xs">
                      {t("settings.communications.enabledDesc")}
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

        <Button type="submit" disabled={updateMutation.isPending}>
          {updateMutation.isPending ? t("common.loading") : t("common.save")}
        </Button>
      </form>
    </Form>
  );
}
