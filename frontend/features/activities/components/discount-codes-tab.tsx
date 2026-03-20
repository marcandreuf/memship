"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Form, FormControl, FormField, FormItem, FormLabel, FormMessage,
} from "@/components/ui/form";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  useDiscountCodes, useCreateDiscountCode, useUpdateDiscountCode, useDeleteDiscountCode,
} from "../hooks/use-activities";
import type { DiscountCodeData } from "../services/activities-api";

const discountSchema = z.object({
  code: z.string().min(1).max(50),
  description: z.string().optional().or(z.literal("")),
  discount_type: z.enum(["percentage", "fixed"]),
  discount_value: z.coerce.number().gt(0),
  max_uses: z.coerce.number().int().min(1).optional().or(z.literal("")),
  valid_from: z.string().optional().or(z.literal("")),
  valid_until: z.string().optional().or(z.literal("")),
});
type DiscountFormValues = z.infer<typeof discountSchema>;

function toLocalDatetime(iso: string) {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric", month: "short", day: "numeric",
  });
}

interface DiscountCodesTabProps {
  activityId: number;
}

export function DiscountCodesTab({ activityId }: DiscountCodesTabProps) {
  const t = useTranslations();
  const { data: codes = [], isLoading } = useDiscountCodes(activityId);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<DiscountCodeData | null>(null);

  if (isLoading) return <p className="text-sm text-muted-foreground">{t("common.loading")}</p>;

  return (
    <div className="space-y-4 table-compact">
      <div className="flex justify-end">
        <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) setEditing(null); }}>
          <DialogTrigger asChild>
            <Button variant="outline" size="sm" onClick={() => setEditing(null)}>
              {t("activities.discounts.create")}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editing ? t("activities.discounts.edit") : t("activities.discounts.create")}
              </DialogTitle>
            </DialogHeader>
            <DiscountForm
              activityId={activityId}
              discount={editing}
              onSuccess={() => { setOpen(false); setEditing(null); }}
            />
          </DialogContent>
        </Dialog>
      </div>

      {!codes.length ? (
        <p className="text-sm text-muted-foreground">{t("activities.discounts.noDiscounts")}</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("activities.discounts.code")}</TableHead>
              <TableHead>{t("activities.discounts.type")}</TableHead>
              <TableHead>{t("activities.discounts.value")}</TableHead>
              <TableHead>{t("activities.discounts.uses")}</TableHead>
              <TableHead>{t("activities.discounts.validFrom")}</TableHead>
              <TableHead>{t("activities.discounts.validUntil")}</TableHead>
              <TableHead>{t("common.actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {codes.map((dc) => (
              <DiscountRow
                key={dc.id}
                activityId={activityId}
                discount={dc}
                onEdit={() => { setEditing(dc); setOpen(true); }}
              />
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

function DiscountForm({
  activityId, discount, onSuccess,
}: {
  activityId: number;
  discount: DiscountCodeData | null;
  onSuccess: () => void;
}) {
  const t = useTranslations();
  const createMutation = useCreateDiscountCode(activityId);
  const updateMutation = useUpdateDiscountCode(activityId);

  const form = useForm<DiscountFormValues>({
    resolver: zodResolver(discountSchema),
    defaultValues: {
      code: discount?.code || "",
      description: discount?.description || "",
      discount_type: (discount?.discount_type as "percentage" | "fixed") || "percentage",
      discount_value: discount?.discount_value ?? 10,
      max_uses: discount?.max_uses ?? "",
      valid_from: discount?.valid_from ? toLocalDatetime(discount.valid_from) : "",
      valid_until: discount?.valid_until ? toLocalDatetime(discount.valid_until) : "",
    },
  });

  async function onSubmit(data: DiscountFormValues) {
    const payload: Record<string, unknown> = {
      code: data.code.toUpperCase(),
      discount_type: data.discount_type,
      discount_value: data.discount_value,
    };
    if (data.description) payload.description = data.description;
    if (data.max_uses !== "" && data.max_uses !== undefined) payload.max_uses = Number(data.max_uses);
    if (data.valid_from) payload.valid_from = new Date(data.valid_from).toISOString();
    if (data.valid_until) payload.valid_until = new Date(data.valid_until).toISOString();

    if (discount) {
      await updateMutation.mutateAsync({ codeId: discount.id, data: payload });
    } else {
      await createMutation.mutateAsync(payload);
    }
    onSuccess();
  }

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField control={form.control} name="code" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.discounts.code")}</FormLabel><FormControl><Input {...field} className="uppercase" /></FormControl><FormMessage /></FormItem>
        )} />
        <FormField control={form.control} name="description" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.description")}</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField control={form.control} name="discount_type" render={({ field }) => (
            <FormItem>
              <FormLabel>{t("activities.discounts.type")}</FormLabel>
              <FormControl>
                <select className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" {...field}>
                  <option value="percentage">{t("activities.discounts.percentage")}</option>
                  <option value="fixed">{t("activities.discounts.fixed")}</option>
                </select>
              </FormControl>
              <FormMessage />
            </FormItem>
          )} />
          <FormField control={form.control} name="discount_value" render={({ field }) => (
            <FormItem><FormLabel>{t("activities.discounts.value")}</FormLabel><FormControl><Input type="number" min={0} step="0.01" {...field} /></FormControl><FormMessage /></FormItem>
          )} />
        </div>
        <FormField control={form.control} name="max_uses" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.discounts.maxUses")}</FormLabel><FormControl><Input type="number" min={1} placeholder={t("activities.discounts.unlimited")} {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField control={form.control} name="valid_from" render={({ field }) => (
            <FormItem><FormLabel>{t("activities.discounts.validFrom")}</FormLabel><FormControl><Input type="datetime-local" {...field} /></FormControl><FormMessage /></FormItem>
          )} />
          <FormField control={form.control} name="valid_until" render={({ field }) => (
            <FormItem><FormLabel>{t("activities.discounts.validUntil")}</FormLabel><FormControl><Input type="datetime-local" {...field} /></FormControl><FormMessage /></FormItem>
          )} />
        </div>
        <Button type="submit" disabled={isPending} className="w-full">
          {isPending ? t("common.loading") : t("common.save")}
        </Button>
      </form>
    </Form>
  );
}

function DiscountRow({
  activityId, discount, onEdit,
}: {
  activityId: number;
  discount: DiscountCodeData;
  onEdit: () => void;
}) {
  const t = useTranslations();
  const deleteMutation = useDeleteDiscountCode(activityId);

  return (
    <TableRow>
      <TableCell><Badge variant="outline" className="font-mono">{discount.code}</Badge></TableCell>
      <TableCell>{discount.discount_type === "percentage" ? t("activities.discounts.percentage") : t("activities.discounts.fixed")}</TableCell>
      <TableCell>{discount.discount_type === "percentage" ? `${discount.discount_value}%` : `${Number(discount.discount_value).toFixed(2)} EUR`}</TableCell>
      <TableCell>{discount.current_uses}{discount.max_uses ? ` / ${discount.max_uses}` : ""}</TableCell>
      <TableCell>{discount.valid_from ? formatDate(discount.valid_from) : "—"}</TableCell>
      <TableCell>{discount.valid_until ? formatDate(discount.valid_until) : "—"}</TableCell>
      <TableCell>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onEdit}>{t("common.edit")}</Button>
          <Button
            variant="outline" size="sm"
            onClick={async () => {
              if (confirm(t("activities.actions.confirmDelete"))) {
                await deleteMutation.mutateAsync(discount.id);
              }
            }}
            disabled={deleteMutation.isPending}
          >
            {t("common.delete")}
          </Button>
        </div>
      </TableCell>
    </TableRow>
  );
}
