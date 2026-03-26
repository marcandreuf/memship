"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
} from "@/components/ui/form";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import { mapApiErrorsToForm } from "@/lib/errors";
import { useAuth } from "@/features/auth/hooks/use-auth";
import {
  useSettings,
  useUpdateSettings,
  useAddress,
  useUpdateAddress,
} from "@/features/settings/hooks/use-settings";
import { MembershipTypesSettings } from "@/features/settings/components/membership-types-settings";
import { PaymentsSettings } from "@/features/settings/components/payments-settings";
import { LogoUpload } from "@/features/settings/components/logo-upload";
import { FormSkeleton } from "@/components/ui/skeletons";

const settingsSchema = z.object({
  name: z.string().min(1).max(255),
  legal_name: z.string().max(255).optional().or(z.literal("")),
  email: z.string().email().optional().or(z.literal("")),
  phone: z.string().max(50).optional().or(z.literal("")),
  website: z.string().max(255).optional().or(z.literal("")),
  tax_id: z.string().max(50).optional().or(z.literal("")),
  // Address
  address_line1: z.string().max(255).optional().or(z.literal("")),
  address_line2: z.string().max(255).optional().or(z.literal("")),
  city: z.string().max(100).optional().or(z.literal("")),
  state_province: z.string().max(100).optional().or(z.literal("")),
  postal_code: z.string().max(20).optional().or(z.literal("")),
  country: z.string().max(3).optional().or(z.literal("")),
  // Localization
  locale: z.string(),
  timezone: z.string(),
  currency: z.string(),
  date_format: z.string(),
  brand_color: z.string().regex(/^#[0-9a-fA-F]{6}$/).optional().or(z.literal("")),
  logo_url: z.string().max(500).optional().or(z.literal("")),
});

type SettingsFormValues = z.infer<typeof settingsSchema>;

const ADDRESS_FIELDS = ["address_line1", "address_line2", "city", "state_province", "postal_code", "country"] as const;

export default function SettingsPage() {
  const t = useTranslations();
  const { user } = useAuth();
  const { data: settings, isLoading } = useSettings();
  const updateMutation = useUpdateSettings();
  const { data: address } = useAddress();
  const updateAddressMutation = useUpdateAddress();

  const form = useForm<SettingsFormValues>({
    resolver: zodResolver(settingsSchema),
    defaultValues: {
      name: "", legal_name: "", email: "", phone: "", website: "",
      tax_id: "", address_line1: "", address_line2: "", city: "",
      state_province: "", postal_code: "", country: "ES",
      locale: "es", timezone: "Europe/Madrid", currency: "EUR",
      date_format: "DD/MM/YYYY", brand_color: "", logo_url: "",
    },
  });

  useEffect(() => {
    if (settings) {
      form.reset({
        name: settings.name || "",
        legal_name: settings.legal_name || "",
        email: settings.email || "",
        phone: settings.phone || "",
        website: settings.website || "",
        tax_id: settings.tax_id || "",
        address_line1: address?.address_line1 || "",
        address_line2: address?.address_line2 || "",
        city: address?.city || "",
        state_province: address?.state_province || "",
        postal_code: address?.postal_code || "",
        country: address?.country || "ES",
        locale: settings.locale || "es",
        timezone: settings.timezone || "Europe/Madrid",
        currency: settings.currency || "EUR",
        date_format: settings.date_format || "DD/MM/YYYY",
        brand_color: settings.brand_color || "",
        logo_url: settings.logo_url || "",
      });
    }
  }, [settings, address, form]);

  const isAdmin = user?.role === "admin" || user?.role === "super_admin";
  const isSuperAdmin = user?.role === "super_admin";

  if (!isAdmin) {
    return (
      <div className="py-8 text-center text-muted-foreground">
        {t("settings.noAccess")}
      </div>
    );
  }

  if (isLoading) {
    return <FormSkeleton fields={6} />;
  }

  async function onSubmit(data: SettingsFormValues) {
    // Split settings vs address fields
    const settingsPayload: Record<string, unknown> = {};
    const addressPayload: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(data)) {
      if (ADDRESS_FIELDS.includes(key as typeof ADDRESS_FIELDS[number])) {
        if (value !== "" && value !== undefined) addressPayload[key] = value;
      } else {
        if (value !== "" && value !== undefined) settingsPayload[key] = value;
      }
    }
    try {
      await updateMutation.mutateAsync(settingsPayload);
      // Save address if any address field is filled
      if (Object.keys(addressPayload).length > 0) {
        await updateAddressMutation.mutateAsync(addressPayload);
      }
      toast.success(t("toast.success.saved"));
    } catch (error) {
      mapApiErrorsToForm(error, form);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">{t("settings.title")}</h1>

      <Tabs defaultValue={isSuperAdmin ? "organization" : "membership-types"}>
        <TabsList>
          {isSuperAdmin && (
            <TabsTrigger value="organization">{t("settings.organization")}</TabsTrigger>
          )}
          {isSuperAdmin && (
            <TabsTrigger value="payments">{t("settings.payments")}</TabsTrigger>
          )}
          <TabsTrigger value="membership-types">{t("nav.membershipTypes")}</TabsTrigger>
        </TabsList>

        {isSuperAdmin && <TabsContent value="organization">
          <div className="space-y-4">
            {/* Org Info + Address — two forms side by side conceptually */}
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                {/* Organization Info */}
                <Card>
                  <CardHeader className="py-3 px-4">
                    <CardTitle className="text-base">{t("settings.orgInfo")}</CardTitle>
                  </CardHeader>
                  <CardContent className="grid gap-3 sm:grid-cols-2 px-4 pb-4 pt-0">
                    <FormField control={form.control} name="name" render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t("settings.name")}</FormLabel>
                        <FormControl><Input {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )} />
                    <FormField control={form.control} name="legal_name" render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t("settings.legalName")}</FormLabel>
                        <FormControl><Input {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )} />
                    <FormField control={form.control} name="email" render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t("settings.email")}</FormLabel>
                        <FormControl><Input type="email" {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )} />
                    <FormField control={form.control} name="phone" render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t("settings.phone")}</FormLabel>
                        <FormControl><Input {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )} />
                    <FormField control={form.control} name="website" render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t("settings.website")}</FormLabel>
                        <FormControl><Input {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )} />
                    <FormField control={form.control} name="tax_id" render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t("settings.taxId")}</FormLabel>
                        <FormControl><Input {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )} />
                  </CardContent>
                </Card>

                {/* Address */}
                <Card>
                  <CardHeader className="py-3 px-4">
                    <CardTitle className="text-base">{t("settings.address")}</CardTitle>
                  </CardHeader>
                  <CardContent className="grid gap-3 sm:grid-cols-3 px-4 pb-4 pt-0">
                    <FormField control={form.control} name="address_line1" render={({ field }) => (
                      <FormItem className="sm:col-span-2">
                        <FormLabel>{t("settings.addressLine1")}</FormLabel>
                        <FormControl><Input {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )} />
                    <FormField control={form.control} name="address_line2" render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t("settings.addressLine2")}</FormLabel>
                        <FormControl><Input {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )} />
                    <FormField control={form.control} name="city" render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t("settings.city")}</FormLabel>
                        <FormControl><Input {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )} />
                    <FormField control={form.control} name="state_province" render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t("settings.stateProvince")}</FormLabel>
                        <FormControl><Input {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )} />
                    <FormField control={form.control} name="postal_code" render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t("settings.postalCode")}</FormLabel>
                        <FormControl><Input {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )} />
                    <FormField control={form.control} name="country" render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t("settings.country")}</FormLabel>
                        <FormControl><Input {...field} placeholder="ES" /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )} />
                  </CardContent>
                </Card>

                {/* Localization — inline label + value */}
                <Card>
                  <CardHeader className="py-3 px-4">
                    <CardTitle className="text-base">{t("settings.localization")}</CardTitle>
                  </CardHeader>
                  <CardContent className="grid gap-3 sm:grid-cols-2 px-4 pb-4 pt-0">
                    <FormField control={form.control} name="locale" render={({ field }) => (
                      <FormItem>
                        <div className="flex items-center gap-3">
                          <FormLabel className="min-w-28 shrink-0 mt-0">{t("settings.locale")}</FormLabel>
                          <Select onValueChange={field.onChange} value={field.value}>
                            <FormControl><SelectTrigger><SelectValue /></SelectTrigger></FormControl>
                            <SelectContent>
                              <SelectItem value="es">Espa&ntilde;ol</SelectItem>
                              <SelectItem value="ca">Catal&agrave;</SelectItem>
                              <SelectItem value="en">English</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <p className="text-xs text-muted-foreground">{t("settings.localeHint")}</p>
                        <FormMessage />
                      </FormItem>
                    )} />
                    <FormField control={form.control} name="timezone" render={({ field }) => (
                      <FormItem className="flex items-center gap-3">
                        <FormLabel className="min-w-28 shrink-0 mt-0">{t("settings.timezone")}</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl><SelectTrigger><SelectValue /></SelectTrigger></FormControl>
                          <SelectContent>
                            <SelectItem value="Europe/Madrid">Europe/Madrid</SelectItem>
                            <SelectItem value="Europe/London">Europe/London</SelectItem>
                            <SelectItem value="Europe/Paris">Europe/Paris</SelectItem>
                            <SelectItem value="Europe/Berlin">Europe/Berlin</SelectItem>
                            <SelectItem value="America/New_York">America/New_York</SelectItem>
                            <SelectItem value="America/Los_Angeles">America/Los_Angeles</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )} />
                    <FormField control={form.control} name="currency" render={({ field }) => (
                      <FormItem className="flex items-center gap-3">
                        <FormLabel className="min-w-28 shrink-0 mt-0">{t("settings.currency")}</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl><SelectTrigger><SelectValue /></SelectTrigger></FormControl>
                          <SelectContent>
                            <SelectItem value="EUR">EUR</SelectItem>
                            <SelectItem value="USD">USD</SelectItem>
                            <SelectItem value="GBP">GBP</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )} />
                    <FormField control={form.control} name="date_format" render={({ field }) => (
                      <FormItem className="flex items-center gap-3">
                        <FormLabel className="min-w-28 shrink-0 mt-0">{t("settings.dateFormat")}</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl><SelectTrigger><SelectValue /></SelectTrigger></FormControl>
                          <SelectContent>
                            <SelectItem value="DD/MM/YYYY">DD/MM/YYYY</SelectItem>
                            <SelectItem value="MM/DD/YYYY">MM/DD/YYYY</SelectItem>
                            <SelectItem value="YYYY-MM-DD">YYYY-MM-DD</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )} />
                  </CardContent>
                </Card>

                {/* Branding */}
                <Card>
                  <CardHeader className="py-3 px-4">
                    <CardTitle className="text-base">{t("settings.branding")}</CardTitle>
                  </CardHeader>
                  <CardContent className="grid gap-3 sm:grid-cols-2 px-4 pb-4 pt-0">
                    <FormField control={form.control} name="brand_color" render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t("settings.brandColor")}</FormLabel>
                        <FormControl>
                          <div className="flex gap-2">
                            <Input type="color" className="w-12 h-10 p-1" value={field.value || "#000000"} onChange={(e) => field.onChange(e.target.value)} />
                            <Input {...field} placeholder="#3B82F6" className="flex-1" />
                          </div>
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )} />
                    <FormItem>
                      <FormLabel>{t("settings.logoUrl")}</FormLabel>
                      <LogoUpload logoUrl={settings?.logo_url ?? null} />
                    </FormItem>
                  </CardContent>
                </Card>

                <Button type="submit" disabled={updateMutation.isPending || updateAddressMutation.isPending}>
                  {(updateMutation.isPending || updateAddressMutation.isPending) ? t("common.loading") : t("common.save")}
                </Button>
              </form>
            </Form>

          </div>
        </TabsContent>}

        {isSuperAdmin && <TabsContent value="payments">
          <PaymentsSettings />
        </TabsContent>}

        <TabsContent value="membership-types">
          <MembershipTypesSettings />
        </TabsContent>
      </Tabs>
    </div>
  );
}
