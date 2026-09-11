"use client";

import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { useZodResolver } from "@/hooks/use-zod-resolver";
import { z } from "zod";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DecimalInput } from "@/components/ui/decimal-input";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { useQueryClient } from "@tanstack/react-query";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { ClientApiError } from "@/lib/client-api";
import { mapApiErrorsToForm } from "@/lib/errors";
import { useMembershipTypes } from "@/features/members/hooks/use-members";
import { useCreateSpace, useUpdateSpace } from "../hooks/use-bookings";
import { updateSpace, type Space } from "../services/bookings-api";

const toTimeInput = (s: string | null | undefined) => (s ? s.slice(0, 5) : "");

const spaceSchema = z
  .object({
    name: z.string().min(1).max(200),
    space_type: z.string().max(50),
    description: z.string().max(2000),
    // Left empty the space is free. Kept as a string so "empty" and "0" stay
    // distinguishable — 0 is a deliberate free price, not a missing one.
    price: z
      .string()
      .refine(
        (v) => v === "" || (!Number.isNaN(Number(v)) && Number(v) >= 0),
        "validation.notANumber"
      ),
    open_time: z.string().regex(/^\d{2}:\d{2}$/, "validation.invalidTime"),
    close_time: z.string().regex(/^\d{2}:\d{2}$/, "validation.invalidTime"),
    // No selection means no restriction, the same reading the backend gives an
    // empty array — so there is no "nobody may book this" state to fall into.
    allowed_membership_types: z.array(z.number()),
    is_active: z.boolean(),
  })
  .superRefine((data, ctx) => {
    if (data.open_time && data.close_time && data.close_time <= data.open_time) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["close_time"],
        message: "validation.closeTimeBeforeOpen",
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
  const qc = useQueryClient();
  const [confirmDialog, confirmAction] = useConfirmDialog();
  const { data: membershipTypes } = useMembershipTypes();
  const activeTypes = (membershipTypes ?? []).filter((mt) => mt.is_active);

  const form = useForm<SpaceFormValues>({
    resolver: useZodResolver(spaceSchema),
    defaultValues: {
      name: space?.name ?? "",
      space_type: space?.space_type ?? "",
      description: space?.description ?? "",
      price: space?.price != null ? String(space.price) : "",
      open_time: toTimeInput(space?.open_time) || "08:00",
      close_time: toTimeInput(space?.close_time) || "22:00",
      allowed_membership_types: space?.allowed_membership_types ?? [],
      is_active: space?.is_active ?? true,
    },
  });

  async function onSubmit(data: SpaceFormValues) {
    const payload = {
      name: data.name,
      space_type: data.space_type || null,
      description: data.description || null,
      price: data.price === "" ? null : Number(data.price),
      open_time: data.open_time,
      close_time: data.close_time,
      allowed_membership_types: data.allowed_membership_types,
      is_active: data.is_active,
    };
    try {
      if (space) {
        // The raw call so the expected 409 — upcoming slots outside the new
        // hours — skips the global error toast and reaches the confirm below.
        await updateSpace(space.id, payload);
        qc.invalidateQueries({ queryKey: ["spaces"] });
        qc.invalidateQueries({ queryKey: ["space", space.id] });
      } else {
        await createMutation.mutateAsync(payload);
      }
      toast.success(t("toast.success.saved"));
      onSuccess();
    } catch (error) {
      if (space && error instanceof ClientApiError && error.status === 409) {
        const detail = error.detail as unknown as {
          slots_outside_hours?: number;
          affected_members?: number;
        };
        confirmAction({
          title: t("bookings.spaces.confirmHours"),
          description:
            t("bookings.spaces.hoursSlotsAffected", {
              count: detail?.slots_outside_hours ?? 0,
            }) +
            " " +
            t("bookings.spaces.deleteAffected", {
              count: detail?.affected_members ?? 0,
            }),
          cancelLabel: t("common.cancel"),
          confirmLabel: t("common.save"),
          onConfirm: async () => {
            try {
              await updateMutation.mutateAsync({
                id: space.id,
                data: payload,
                force: true,
              });
              toast.success(t("toast.success.saved"));
              onSuccess();
            } catch {
              /* global handler */
            }
          },
        });
        return;
      }
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
                <Input placeholder={t("bookings.spaces.typePlaceholder")} {...field} />
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
        <FormField
          control={form.control}
          name="price"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t("bookings.spaces.price")}</FormLabel>
              <FormControl>
                <DecimalInput placeholder="0.00" {...field} />
              </FormControl>
              <FormDescription>
                {t("bookings.spaces.priceHint")}
              </FormDescription>
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
          name="allowed_membership_types"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t("bookings.spaces.allowedTypes")}</FormLabel>
              <FormDescription>
                {t("bookings.spaces.allowedTypesHint")}
              </FormDescription>
              {activeTypes.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  {t("bookings.spaces.allowedTypesNone")}
                </p>
              ) : (
                <div className="grid gap-2 sm:grid-cols-2">
                  {activeTypes.map((mt) => (
                    <label
                      key={mt.id}
                      className="flex items-center gap-2 text-sm"
                    >
                      <Checkbox
                        checked={field.value.includes(mt.id)}
                        onCheckedChange={(checked) =>
                          field.onChange(
                            checked
                              ? [...field.value, mt.id]
                              : field.value.filter((id) => id !== mt.id)
                          )
                        }
                      />
                      {mt.name}
                    </label>
                  ))}
                </div>
              )}
              <FormMessage />
            </FormItem>
          )}
        />
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
      {confirmDialog}
    </Form>
  );
}
