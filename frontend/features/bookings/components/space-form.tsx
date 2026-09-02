"use client";

import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { mapApiErrorsToForm } from "@/lib/errors";
import { useCreateSpace, useUpdateSpace } from "../hooks/use-bookings";
import type { Space } from "../services/bookings-api";

const toTimeInput = (s: string | null | undefined) => (s ? s.slice(0, 5) : "");

const spaceSchema = z
  .object({
    name: z.string().min(1).max(200),
    space_type: z.string().max(50),
    description: z.string().max(2000),
    open_time: z.string().regex(/^\d{2}:\d{2}$/, "HH:MM"),
    close_time: z.string().regex(/^\d{2}:\d{2}$/, "HH:MM"),
    is_active: z.boolean(),
  })
  .superRefine((data, ctx) => {
    if (data.open_time && data.close_time && data.close_time <= data.open_time) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["close_time"],
        message: "close after open",
      });
    }
  });

type SpaceFormValues = z.infer<typeof spaceSchema>;

export function SpaceForm({
  space,
  onSuccess,
  onCancel,
}: {
  space: Space | null;
  onSuccess: () => void;
  /**
   * Present when the form edits in place inside a card, where the read view it
   * replaced has to be reachable again. The create dialog has its own dismiss,
   * so it passes nothing and keeps the single full-width save button.
   */
  onCancel?: () => void;
}) {
  const t = useTranslations();
  const createMutation = useCreateSpace();
  const updateMutation = useUpdateSpace();

  const form = useForm<SpaceFormValues>({
    resolver: zodResolver(spaceSchema),
    defaultValues: {
      name: space?.name ?? "",
      space_type: space?.space_type ?? "",
      description: space?.description ?? "",
      open_time: toTimeInput(space?.open_time) || "08:00",
      close_time: toTimeInput(space?.close_time) || "22:00",
      is_active: space?.is_active ?? true,
    },
  });

  async function onSubmit(data: SpaceFormValues) {
    const payload = {
      name: data.name,
      space_type: data.space_type || null,
      description: data.description || null,
      open_time: data.open_time,
      close_time: data.close_time,
      is_active: data.is_active,
    };
    try {
      if (space) {
        await updateMutation.mutateAsync({ id: space.id, data: payload });
      } else {
        await createMutation.mutateAsync(payload);
      }
      toast.success(t("toast.success.saved"));
      onSuccess();
    } catch (error) {
      mapApiErrorsToForm(error, form);
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t("bookings.spaces.name")}</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="space_type"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t("bookings.spaces.type")}</FormLabel>
              <FormControl>
                <Input placeholder="pitch, court, room…" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t("bookings.spaces.description")}</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="open_time"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("bookings.spaces.openTime")}</FormLabel>
                <FormControl>
                  <Input type="time" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="close_time"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("bookings.spaces.closeTime")}</FormLabel>
                <FormControl>
                  <Input type="time" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
        <FormField
          control={form.control}
          name="is_active"
          render={({ field }) => (
            <FormItem className="flex items-center gap-2">
              <FormControl>
                <Checkbox
                  checked={field.value}
                  onCheckedChange={field.onChange}
                />
              </FormControl>
              <FormLabel className="!mt-0">
                {t("bookings.spaces.active")}
              </FormLabel>
            </FormItem>
          )}
        />
        {onCancel ? (
          <div className="flex gap-3">
            <Button type="submit" disabled={isPending}>
              {isPending ? t("common.loading") : t("common.save")}
            </Button>
            <Button type="button" variant="outline" onClick={onCancel}>
              {t("common.cancel")}
            </Button>
          </div>
        ) : (
          <Button type="submit" disabled={isPending} className="w-full">
            {isPending ? t("common.loading") : t("common.save")}
          </Button>
        )}
      </form>
    </Form>
  );
}
