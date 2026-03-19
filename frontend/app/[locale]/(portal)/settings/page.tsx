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
import { useAuth } from "@/features/auth/hooks/use-auth";
import { useSettings, useUpdateSettings } from "@/features/settings/hooks/use-settings";
import { MembershipTypesSettings } from "@/features/settings/components/membership-types-settings";

const settingsSchema = z.object({
  name: z.string().min(1).max(255),
  legal_name: z.string().max(255).optional().or(z.literal("")),
  email: z.string().email().optional().or(z.literal("")),
  phone: z.string().max(50).optional().or(z.literal("")),
  website: z.string().max(255).optional().or(z.literal("")),
  tax_id: z.string().max(50).optional().or(z.literal("")),
  locale: z.string(),
  timezone: z.string(),
  currency: z.string(),
  date_format: z.string(),
  brand_color: z.string().regex(/^#[0-9a-fA-F]{6}$/).optional().or(z.literal("")),
  logo_url: z.string().max(500).optional().or(z.literal("")),
});

type SettingsFormValues = z.infer<typeof settingsSchema>;

export default function SettingsPage() {
  const t = useTranslations();
  const { user } = useAuth();
  const { data: settings, isLoading } = useSettings();
  const updateMutation = useUpdateSettings();

  const form = useForm<SettingsFormValues>({
    resolver: zodResolver(settingsSchema),
    defaultValues: {
      name: "", legal_name: "", email: "", phone: "", website: "",
      tax_id: "", locale: "es", timezone: "Europe/Madrid", currency: "EUR",
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
        locale: settings.locale || "es",
        timezone: settings.timezone || "Europe/Madrid",
        currency: settings.currency || "EUR",
        date_format: settings.date_format || "DD/MM/YYYY",
        brand_color: settings.brand_color || "",
        logo_url: settings.logo_url || "",
      });
    }
  }, [settings, form]);

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
    return <div className="py-8 text-center text-muted-foreground">{t("common.loading")}</div>;
  }

  async function onSubmit(data: SettingsFormValues) {
    const payload: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(data)) {
      if (value !== "") {
        payload[key] = value;
      }
    }
    await updateMutation.mutateAsync(payload);
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">{t("settings.title")}</h1>

      <Tabs defaultValue={isSuperAdmin ? "organization" : "membership-types"}>
        <TabsList>
          {isSuperAdmin && (
            <TabsTrigger value="organization">{t("settings.organization")}</TabsTrigger>
          )}
          <TabsTrigger value="membership-types">{t("nav.membershipTypes")}</TabsTrigger>
        </TabsList>

        {isSuperAdmin && <TabsContent value="organization">
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
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

              <Card>
                <CardHeader className="py-3 px-4">
                  <CardTitle className="text-base">{t("settings.localization")}</CardTitle>
                </CardHeader>
                <CardContent className="grid gap-3 sm:grid-cols-2 px-4 pb-4 pt-0">
                  <FormField control={form.control} name="locale" render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("settings.locale")}</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl><SelectTrigger><SelectValue /></SelectTrigger></FormControl>
                        <SelectContent>
                          <SelectItem value="es">Espa&ntilde;ol</SelectItem>
                          <SelectItem value="ca">Catal&agrave;</SelectItem>
                          <SelectItem value="en">English</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )} />
                  <FormField control={form.control} name="timezone" render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("settings.timezone")}</FormLabel>
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
                    <FormItem>
                      <FormLabel>{t("settings.currency")}</FormLabel>
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
                    <FormItem>
                      <FormLabel>{t("settings.dateFormat")}</FormLabel>
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
                  <FormField control={form.control} name="logo_url" render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("settings.logoUrl")}</FormLabel>
                      <FormControl><Input {...field} placeholder="https://..." /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )} />
                </CardContent>
              </Card>

              <Button type="submit" disabled={updateMutation.isPending}>
                {updateMutation.isPending ? t("common.loading") : t("common.save")}
              </Button>
              {updateMutation.isSuccess && (
                <p className="text-sm text-green-600">{t("settings.saved")}</p>
              )}
            </form>
          </Form>
        </TabsContent>}

        <TabsContent value="membership-types">
          <MembershipTypesSettings />
        </TabsContent>
      </Tabs>
    </div>
  );
}
