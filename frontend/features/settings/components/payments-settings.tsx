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

const paymentsSchema = z.object({
  // Invoicing
  invoice_prefix: z.string().min(1).max(10),
  invoice_next_number: z.coerce.number().int().min(1),
  invoice_annual_reset: z.boolean(),
  default_vat_rate: z.coerce.number().min(0).max(100),
  // Banking
  bank_name: z.string().max(255).optional().or(z.literal("")),
  bank_iban: z.string().max(34).optional().or(z.literal("")),
  bank_bic: z.string().max(11).optional().or(z.literal("")),
});

type PaymentsFormValues = z.infer<typeof paymentsSchema>;

export function PaymentsSettings() {
  const t = useTranslations();
  const { data: settings, isLoading } = useSettings();
  const updateMutation = useUpdateSettings();

  const form = useForm<PaymentsFormValues>({
    resolver: zodResolver(paymentsSchema),
    defaultValues: {
      invoice_prefix: "FAC",
      invoice_next_number: 1,
      invoice_annual_reset: true,
      default_vat_rate: 21,
      bank_name: "",
      bank_iban: "",
      bank_bic: "",
    },
  });

  useEffect(() => {
    if (settings) {
      form.reset({
        invoice_prefix: settings.invoice_prefix || "FAC",
        invoice_next_number: settings.invoice_next_number || 1,
        invoice_annual_reset: settings.invoice_annual_reset ?? true,
        default_vat_rate: settings.default_vat_rate ?? 21,
        bank_name: settings.bank_name || "",
        bank_iban: settings.bank_iban || "",
        bank_bic: settings.bank_bic || "",
      });
    }
  }, [settings, form]);

  if (isLoading) return <FormSkeleton fields={4} />;

  async function onSubmit(data: PaymentsFormValues) {
    const payload: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(data)) {
      if (value !== "" && value !== undefined) {
        payload[key] = value;
      }
    }
    try {
      await updateMutation.mutateAsync(payload);
      toast.success(t("toast.success.saved"));
    } catch (error) {
      mapApiErrorsToForm(error, form);
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        {/* Invoicing */}
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-base">{t("settings.invoicing")}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2 px-4 pb-4 pt-0">
            <FormField control={form.control} name="invoice_prefix" render={({ field }) => (
              <FormItem>
                <FormLabel>{t("settings.invoicePrefix")}</FormLabel>
                <FormControl><Input {...field} placeholder="FAC" className="font-mono" /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="invoice_next_number" render={({ field }) => (
              <FormItem>
                <FormLabel>{t("settings.invoiceNextNumber")}</FormLabel>
                <FormControl><Input type="number" min={1} {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="default_vat_rate" render={({ field }) => (
              <FormItem>
                <FormLabel>{t("settings.defaultVatRate")}</FormLabel>
                <FormControl>
                  <div className="flex items-center gap-2">
                    <Input type="number" min={0} max={100} step={0.01} {...field} className="flex-1" />
                    <span className="text-sm text-muted-foreground">%</span>
                  </div>
                </FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="invoice_annual_reset" render={({ field }) => (
              <FormItem className="flex items-center justify-between gap-3 rounded-lg border p-3">
                <div>
                  <FormLabel className="mt-0">{t("settings.invoiceAnnualReset")}</FormLabel>
                  <FormDescription className="text-xs">
                    {t("settings.invoiceAnnualResetDesc")}
                  </FormDescription>
                </div>
                <FormControl>
                  <Switch checked={field.value} onCheckedChange={field.onChange} />
                </FormControl>
              </FormItem>
            )} />
          </CardContent>
        </Card>

        {/* Banking */}
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-base">{t("settings.banking")}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2 px-4 pb-4 pt-0">
            <FormField control={form.control} name="bank_name" render={({ field }) => (
              <FormItem>
                <FormLabel>{t("settings.bankName")}</FormLabel>
                <FormControl><Input {...field} placeholder="CaixaBank" /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="bank_iban" render={({ field }) => (
              <FormItem>
                <FormLabel>{t("settings.bankIban")}</FormLabel>
                <FormControl><Input {...field} placeholder="ES9121000418450200051332" className="font-mono" /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="bank_bic" render={({ field }) => (
              <FormItem>
                <FormLabel>{t("settings.bankBic")}</FormLabel>
                <FormControl><Input {...field} placeholder="CAIXESBBXXX" className="font-mono" /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
          </CardContent>
        </Card>

        <Button type="submit" disabled={updateMutation.isPending}>
          {updateMutation.isPending ? t("common.loading") : t("common.save")}
        </Button>
      </form>
    </Form>
  );
}
