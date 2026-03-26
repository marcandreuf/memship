"use client";

import { useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DecimalInput } from "@/components/ui/decimal-input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Form, FormControl, FormField, FormItem, FormLabel, FormMessage,
} from "@/components/ui/form";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { TabContentSkeleton } from "@/components/ui/skeletons";
import { toast } from "sonner";
import { mapApiErrorsToForm } from "@/lib/errors";
import { useFormatters } from "@/hooks/use-formatters";
import { useReceipts, useCreateReceipt } from "@/features/receipts/hooks/use-receipts";

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  new: "outline",
  pending: "secondary",
  emitted: "secondary",
  paid: "default",
  returned: "destructive",
  cancelled: "destructive",
  overdue: "destructive",
};

const createSchema = z.object({
  origin: z.string().min(1),
  description: z.string().min(1).max(500),
  base_amount: z.coerce.number().min(0),
  vat_rate: z.coerce.number().min(0).max(100),
  emission_date: z.string().min(1),
  due_date: z.string().optional().or(z.literal("")),
  notes: z.string().optional().or(z.literal("")),
});

interface MemberReceiptsTabProps {
  memberId: number;
}

export function MemberReceiptsTab({ memberId }: MemberReceiptsTabProps) {
  const t = useTranslations();
  const router = useRouter();
  const [createOpen, setCreateOpen] = useState(false);

  const params = useMemo(() => {
    const p = new URLSearchParams();
    p.set("member_id", String(memberId));
    p.set("per_page", "50");
    return p;
  }, [memberId]);

  const { data, isLoading } = useReceipts(params);
  const { formatCurrency, formatDate } = useFormatters();

  if (isLoading) return <TabContentSkeleton />;

  const items = data?.items || [];

  return (
    <div className="space-y-4 table-compact">
      <div className="flex justify-end">
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button variant="outline" size="sm">{t("receipts.createReceipt")}</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t("receipts.createReceipt")}</DialogTitle>
            </DialogHeader>
            <CreateMemberReceiptForm
              memberId={memberId}
              t={t}
              onSuccess={() => setCreateOpen(false)}
            />
          </DialogContent>
        </Dialog>
      </div>

      {!items.length ? (
        <p className="text-sm text-muted-foreground py-4">{t("receipts.noReceipts")}</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("receipts.receiptNumber")}</TableHead>
              <TableHead>{t("receipts.description")}</TableHead>
              <TableHead className="text-right">{t("receipts.total")}</TableHead>
              <TableHead>{t("receipts.status")}</TableHead>
              <TableHead>{t("receipts.emissionDate")}</TableHead>
              <TableHead>{t("receipts.paymentDate")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((r) => {
              const statusLabel = t(`receipts.status${r.status.charAt(0).toUpperCase() + r.status.slice(1)}`);
              return (
                <TableRow
                  key={r.id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => router.push(`/receipts/${r.id}`)}
                >
                  <TableCell className="font-mono text-sm">{r.receipt_number}</TableCell>
                  <TableCell className="max-w-[200px] truncate">{r.description}</TableCell>
                  <TableCell className="text-right font-mono">{formatCurrency(r.total_amount)}</TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANTS[r.status] || "outline"}>{statusLabel}</Badge>
                  </TableCell>
                  <TableCell className="text-sm">{formatDate(r.emission_date)}</TableCell>
                  <TableCell className="text-sm">{formatDate(r.payment_date)}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

function CreateMemberReceiptForm({
  memberId,
  t,
  onSuccess,
}: {
  memberId: number;
  t: (key: string, values?: Record<string, unknown>) => string;
  onSuccess: () => void;
}) {
  const createMutation = useCreateReceipt();

  const form = useForm({
    resolver: zodResolver(createSchema),
    defaultValues: {
      origin: "manual",
      description: "",
      base_amount: "",
      vat_rate: "21",
      emission_date: new Date().toISOString().split("T")[0],
      due_date: "",
      notes: "",
    },
  });

  async function onSubmit(data: z.infer<typeof createSchema>) {
    const payload: Record<string, unknown> = {
      member_id: memberId,
      origin: data.origin,
      description: data.description,
      base_amount: data.base_amount,
      vat_rate: data.vat_rate,
      emission_date: data.emission_date,
    };
    if (data.due_date) payload.due_date = data.due_date;
    if (data.notes) payload.notes = data.notes;

    try {
      await createMutation.mutateAsync(payload);
      toast.success(t("toast.success.saved"));
      onSuccess();
    } catch (error) {
      mapApiErrorsToForm(error, form);
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField control={form.control} name="origin" render={({ field }) => (
          <FormItem>
            <FormLabel>{t("receipts.origin")}</FormLabel>
            <Select onValueChange={field.onChange} value={field.value}>
              <FormControl><SelectTrigger><SelectValue /></SelectTrigger></FormControl>
              <SelectContent>
                <SelectItem value="manual">{t("receipts.originManual")}</SelectItem>
                <SelectItem value="membership">{t("receipts.originMembership")}</SelectItem>
                <SelectItem value="activity">{t("receipts.originActivity")}</SelectItem>
                <SelectItem value="service">{t("receipts.originService")}</SelectItem>
              </SelectContent>
            </Select>
            <FormMessage />
          </FormItem>
        )} />
        <FormField control={form.control} name="description" render={({ field }) => (
          <FormItem>
            <FormLabel>{t("receipts.description")}</FormLabel>
            <FormControl><Input {...field} /></FormControl>
            <FormMessage />
          </FormItem>
        )} />
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField control={form.control} name="base_amount" render={({ field }) => (
            <FormItem>
              <FormLabel>{t("receipts.base")} (€)</FormLabel>
              <FormControl><DecimalInput {...field} /></FormControl>
              <FormMessage />
            </FormItem>
          )} />
          <FormField control={form.control} name="vat_rate" render={({ field }) => (
            <FormItem>
              <FormLabel>{t("receipts.vatRate")} (%)</FormLabel>
              <FormControl><DecimalInput {...field} /></FormControl>
              <FormMessage />
            </FormItem>
          )} />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField control={form.control} name="emission_date" render={({ field }) => (
            <FormItem>
              <FormLabel>{t("receipts.emissionDate")}</FormLabel>
              <FormControl><Input type="date" {...field} /></FormControl>
              <FormMessage />
            </FormItem>
          )} />
          <FormField control={form.control} name="due_date" render={({ field }) => (
            <FormItem>
              <FormLabel>{t("receipts.dueDate")}</FormLabel>
              <FormControl><Input type="date" {...field} /></FormControl>
              <FormMessage />
            </FormItem>
          )} />
        </div>
        <FormField control={form.control} name="notes" render={({ field }) => (
          <FormItem>
            <FormLabel>{t("receipts.notes")}</FormLabel>
            <FormControl><Input {...field} /></FormControl>
            <FormMessage />
          </FormItem>
        )} />
        <Button type="submit" disabled={createMutation.isPending} className="w-full">
          {createMutation.isPending ? t("common.loading") : t("common.save")}
        </Button>
      </form>
    </Form>
  );
}
