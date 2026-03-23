"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "sonner";
import { mapApiErrorsToForm } from "@/lib/errors";
import {
  useCreatePrice,
  useUpdatePrice,
  useDeletePrice,
} from "../hooks/use-activities";
import type { ActivityData, ActivityModalityData, ActivityPriceData } from "../services/activities-api";

const priceSchema = z.object({
  name: z.string().min(1).max(255),
  description: z.string().max(2000).optional().or(z.literal("")),
  amount: z.coerce.number().min(0),
  modality_id: z.coerce.number().int().optional().or(z.literal("")),
  display_order: z.coerce.number().int().min(0),
  is_optional: z.boolean(),
  is_default: z.boolean(),
  valid_from: z.string().optional().or(z.literal("")),
  valid_until: z.string().optional().or(z.literal("")),
});
type PriceFormValues = z.infer<typeof priceSchema>;

function toLocalDatetime(iso: string) {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatAmount(amount: number) {
  return amount === 0 ? null : `${amount.toFixed(2)} EUR`;
}

interface PricesTabProps {
  activityId: number;
  prices: ActivityPriceData[];
  modalities: ActivityModalityData[];
  activity: ActivityData;
  isAdmin: boolean;
}

export function PricesTab({ activityId, prices, modalities, activity, isAdmin }: PricesTabProps) {
  const t = useTranslations();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ActivityPriceData | null>(null);

  // Member view: simple price summary
  if (!isAdmin) {
    if (!prices.length) return null;
    return (
      <div className="space-y-2">
        {prices.filter(p => p.is_visible).map((p) => (
          <div key={p.id} className="flex justify-between">
            <span>{p.name}</span>
            <span className="font-medium">{formatAmount(p.amount) || t("activities.prices.free")}</span>
          </div>
        ))}
      </div>
    );
  }

  // Admin view: full CRUD
  return (
    <div className="space-y-4 table-compact">
      <div className="flex justify-end">
        <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) setEditing(null); }}>
          <DialogTrigger asChild>
            <Button variant="outline" size="sm" onClick={() => setEditing(null)}>
              {t("activities.prices.create")}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editing ? t("activities.prices.edit") : t("activities.prices.create")}
              </DialogTitle>
            </DialogHeader>
            <PriceForm
              activityId={activityId}
              modalities={modalities}
              price={editing}
              onSuccess={() => { setOpen(false); setEditing(null); }}
            />
          </DialogContent>
        </Dialog>
      </div>

      {!prices.length ? (
        <p className="text-sm text-muted-foreground">{t("activities.prices.noPrices")}</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("activities.prices.name")}</TableHead>
              <TableHead>{t("activities.prices.amount")}</TableHead>
              <TableHead>{t("activities.prices.modality")}</TableHead>
              <TableHead>{t("activities.prices.validFrom")}</TableHead>
              <TableHead>{t("activities.prices.validUntil")}</TableHead>
              <TableHead>{t("activities.prices.isDefault")}</TableHead>
              <TableHead>{t("activities.prices.isOptional")}</TableHead>
              <TableHead>{t("common.actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {prices.map((p) => (
              <PriceRow
                key={p.id}
                activityId={activityId}
                modalities={modalities}
                price={p}
                onEdit={() => { setEditing(p); setOpen(true); }}
              />
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

function PriceForm({
  activityId,
  modalities,
  price,
  onSuccess,
}: {
  activityId: number;
  modalities: ActivityModalityData[];
  price: ActivityPriceData | null;
  onSuccess: () => void;
}) {
  const t = useTranslations();
  const createMutation = useCreatePrice(activityId);
  const updateMutation = useUpdatePrice(activityId);

  const form = useForm<PriceFormValues>({
    resolver: zodResolver(priceSchema),
    defaultValues: {
      name: price?.name || "",
      description: price?.description || "",
      amount: price?.amount ?? 0,
      modality_id: price?.modality_id ?? "",
      display_order: price?.display_order ?? 1,
      is_optional: price?.is_optional ?? false,
      is_default: price?.is_default ?? false,
      valid_from: price?.valid_from ? toLocalDatetime(price.valid_from) : "",
      valid_until: price?.valid_until ? toLocalDatetime(price.valid_until) : "",
    },
  });

  async function onSubmit(data: PriceFormValues) {
    const payload: Record<string, unknown> = {
      name: data.name,
      amount: data.amount,
      display_order: data.display_order,
      is_optional: data.is_optional,
      is_default: data.is_default,
    };
    if (data.description) payload.description = data.description;
    if (data.modality_id !== "" && data.modality_id !== undefined) payload.modality_id = Number(data.modality_id);
    if (data.valid_from) payload.valid_from = new Date(data.valid_from).toISOString();
    if (data.valid_until) payload.valid_until = new Date(data.valid_until).toISOString();

    try {
      if (price) {
        await updateMutation.mutateAsync({ priceId: price.id, data: payload });
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
        <FormField control={form.control} name="name" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.prices.name")}</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <FormField control={form.control} name="description" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.description")}</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <FormField control={form.control} name="amount" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.prices.amount")}</FormLabel><FormControl><Input type="number" min={0} step="0.01" {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        {modalities.length > 0 && (
          <FormField control={form.control} name="modality_id" render={({ field }) => (
            <FormItem>
              <FormLabel>{t("activities.prices.modality")}</FormLabel>
              <FormControl>
                <select
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={field.value ?? ""}
                  onChange={(e) => field.onChange(e.target.value === "" ? "" : Number(e.target.value))}
                >
                  <option value="">{t("activities.prices.activityLevel")}</option>
                  {modalities.map((m) => (
                    <option key={m.id} value={m.id}>{m.name}</option>
                  ))}
                </select>
              </FormControl>
              <FormMessage />
            </FormItem>
          )} />
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField control={form.control} name="valid_from" render={({ field }) => (
            <FormItem><FormLabel>{t("activities.prices.validFrom")}</FormLabel><FormControl><Input type="datetime-local" {...field} /></FormControl><FormMessage /></FormItem>
          )} />
          <FormField control={form.control} name="valid_until" render={({ field }) => (
            <FormItem><FormLabel>{t("activities.prices.validUntil")}</FormLabel><FormControl><Input type="datetime-local" {...field} /></FormControl><FormMessage /></FormItem>
          )} />
        </div>
        <FormField control={form.control} name="is_default" render={({ field }) => (
          <FormItem className="flex items-center gap-2">
            <FormControl><Checkbox checked={field.value} onCheckedChange={field.onChange} /></FormControl>
            <FormLabel className="!mt-0">{t("activities.prices.isDefault")}</FormLabel><FormMessage />
          </FormItem>
        )} />
        <FormField control={form.control} name="is_optional" render={({ field }) => (
          <FormItem className="flex items-center gap-2">
            <FormControl><Checkbox checked={field.value} onCheckedChange={field.onChange} /></FormControl>
            <FormLabel className="!mt-0">{t("activities.prices.isOptional")}</FormLabel><FormMessage />
          </FormItem>
        )} />
        <Button type="submit" disabled={isPending} className="w-full">
          {isPending ? t("common.loading") : t("common.save")}
        </Button>
      </form>
    </Form>
  );
}

function PriceRow({
  activityId,
  modalities,
  price,
  onEdit,
}: {
  activityId: number;
  modalities: ActivityModalityData[];
  price: ActivityPriceData;
  onEdit: () => void;
}) {
  const t = useTranslations();
  const deleteMutation = useDeletePrice(activityId);
  const modalityName = price.modality_id
    ? modalities.find((m) => m.id === price.modality_id)?.name || "—"
    : t("activities.prices.activityLevel");

  return (
    <TableRow>
      <TableCell className="font-medium">{price.name}</TableCell>
      <TableCell>{formatAmount(price.amount) || t("activities.prices.free")}</TableCell>
      <TableCell>{modalityName}</TableCell>
      <TableCell>{price.valid_from ? formatDate(price.valid_from) : "—"}</TableCell>
      <TableCell>{price.valid_until ? formatDate(price.valid_until) : "—"}</TableCell>
      <TableCell>{price.is_default ? t("common.yes") : t("common.no")}</TableCell>
      <TableCell>{price.is_optional ? t("common.yes") : t("common.no")}</TableCell>
      <TableCell>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onEdit}>{t("common.edit")}</Button>
          <Button
            variant="outline"
            size="sm"
            onClick={async () => {
              if (confirm(t("activities.actions.confirmDelete"))) {
                try {
                  await deleteMutation.mutateAsync(price.id);
                  toast.success(t("toast.success.deleted"));
                } catch { /* global handler shows error toast */ }
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
