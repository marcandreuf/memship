"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import type { ActivityData } from "../services/activities-api";

const editActivitySchema = z.object({
  name: z.string().min(1).max(255),
  short_description: z.string().max(500).optional().or(z.literal("")),
  description: z.string().optional().or(z.literal("")),
  starts_at: z.string().min(1),
  ends_at: z.string().min(1),
  registration_starts_at: z.string().min(1),
  registration_ends_at: z.string().min(1),
  location: z.string().max(255).optional().or(z.literal("")),
  location_details: z.string().optional().or(z.literal("")),
  location_url: z.string().max(500).optional().or(z.literal("")),
  min_participants: z.coerce.number().int().min(0),
  max_participants: z.coerce.number().int().min(1),
  min_age: z.coerce.number().int().min(0).optional().or(z.literal("")),
  max_age: z.coerce.number().int().min(0).optional().or(z.literal("")),
  tax_rate: z.coerce.number().min(0).max(100),
  allow_self_cancellation: z.boolean(),
  self_cancellation_deadline_hours: z.coerce.number().int().min(0).optional().or(z.literal("")),
});

type EditActivityFormValues = z.infer<typeof editActivitySchema>;

function toLocalDatetime(iso: string) {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

interface ActivityEditFormProps {
  activity: ActivityData;
  onSubmit: (data: Record<string, unknown>) => Promise<void>;
  isPending: boolean;
  onCancel?: () => void;
}

export function ActivityEditForm({
  activity,
  onSubmit,
  isPending,
  onCancel,
}: ActivityEditFormProps) {
  const t = useTranslations();

  const form = useForm<EditActivityFormValues>({
    resolver: zodResolver(editActivitySchema),
    defaultValues: {
      name: activity.name,
      short_description: activity.short_description || "",
      description: activity.description || "",
      starts_at: toLocalDatetime(activity.starts_at),
      ends_at: toLocalDatetime(activity.ends_at),
      registration_starts_at: toLocalDatetime(activity.registration_starts_at),
      registration_ends_at: toLocalDatetime(activity.registration_ends_at),
      location: activity.location || "",
      location_details: activity.location_details || "",
      location_url: activity.location_url || "",
      min_participants: activity.min_participants,
      max_participants: activity.max_participants,
      min_age: activity.min_age ?? "",
      max_age: activity.max_age ?? "",
      tax_rate: activity.tax_rate,
      allow_self_cancellation: activity.allow_self_cancellation,
      self_cancellation_deadline_hours: activity.self_cancellation_deadline_hours ?? "",
    },
  });

  const allowSelfCancellation = form.watch("allow_self_cancellation");

  async function handleSubmit(data: EditActivityFormValues) {
    const payload: Record<string, unknown> = {
      name: data.name,
      starts_at: new Date(data.starts_at).toISOString(),
      ends_at: new Date(data.ends_at).toISOString(),
      registration_starts_at: new Date(data.registration_starts_at).toISOString(),
      registration_ends_at: new Date(data.registration_ends_at).toISOString(),
      min_participants: data.min_participants,
      max_participants: data.max_participants,
      tax_rate: data.tax_rate,
      allow_self_cancellation: data.allow_self_cancellation,
      short_description: data.short_description || null,
      description: data.description || null,
      location: data.location || null,
      location_details: data.location_details || null,
      location_url: data.location_url || null,
      min_age: data.min_age !== "" && data.min_age !== undefined ? Number(data.min_age) : null,
      max_age: data.max_age !== "" && data.max_age !== undefined ? Number(data.max_age) : null,
      self_cancellation_deadline_hours: data.allow_self_cancellation && data.self_cancellation_deadline_hours !== "" && data.self_cancellation_deadline_hours !== undefined ? Number(data.self_cancellation_deadline_hours) : null,
    };
    await onSubmit(payload);
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-3">
        <FormField control={form.control} name="name" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.name")}</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <FormField control={form.control} name="short_description" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.shortDescription")}</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <FormField control={form.control} name="description" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.description")}</FormLabel><FormControl><Textarea rows={3} {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField control={form.control} name="starts_at" render={({ field }) => (
            <FormItem><FormLabel>{t("activities.startsAt")}</FormLabel><FormControl><Input type="datetime-local" {...field} /></FormControl><FormMessage /></FormItem>
          )} />
          <FormField control={form.control} name="ends_at" render={({ field }) => (
            <FormItem><FormLabel>{t("activities.endsAt")}</FormLabel><FormControl><Input type="datetime-local" {...field} /></FormControl><FormMessage /></FormItem>
          )} />
          <FormField control={form.control} name="registration_starts_at" render={({ field }) => (
            <FormItem><FormLabel>{t("activities.registrationStartsAt")}</FormLabel><FormControl><Input type="datetime-local" {...field} /></FormControl><FormMessage /></FormItem>
          )} />
          <FormField control={form.control} name="registration_ends_at" render={({ field }) => (
            <FormItem><FormLabel>{t("activities.registrationEndsAt")}</FormLabel><FormControl><Input type="datetime-local" {...field} /></FormControl><FormMessage /></FormItem>
          )} />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField control={form.control} name="location" render={({ field }) => (
            <FormItem><FormLabel>{t("activities.location")}</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
          )} />
          <FormField control={form.control} name="location_details" render={({ field }) => (
            <FormItem><FormLabel>{t("activities.locationDetails")}</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
          )} />
          <FormField control={form.control} name="location_url" render={({ field }) => (
            <FormItem className="sm:col-span-2"><FormLabel>{t("activities.locationUrl")}</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
          )} />
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <FormField control={form.control} name="min_participants" render={({ field }) => (
            <FormItem><FormLabel>{t("activities.minParticipants")}</FormLabel><FormControl><Input type="number" min={0} {...field} /></FormControl><FormMessage /></FormItem>
          )} />
          <FormField control={form.control} name="max_participants" render={({ field }) => (
            <FormItem><FormLabel>{t("activities.maxParticipants")}</FormLabel><FormControl><Input type="number" min={1} {...field} /></FormControl><FormMessage /></FormItem>
          )} />
          <FormField control={form.control} name="tax_rate" render={({ field }) => (
            <FormItem><FormLabel>{t("activities.taxRate")}</FormLabel><FormControl><Input type="number" min={0} max={100} step="0.01" {...field} /></FormControl><FormMessage /></FormItem>
          )} />
          <FormField control={form.control} name="min_age" render={({ field }) => (
            <FormItem><FormLabel>{t("activities.minAge")}</FormLabel><FormControl><Input type="number" min={0} {...field} /></FormControl><FormMessage /></FormItem>
          )} />
          <FormField control={form.control} name="max_age" render={({ field }) => (
            <FormItem><FormLabel>{t("activities.maxAge")}</FormLabel><FormControl><Input type="number" min={0} {...field} /></FormControl><FormMessage /></FormItem>
          )} />
        </div>
        <FormField control={form.control} name="allow_self_cancellation" render={({ field }) => (
          <FormItem className="flex items-center gap-2">
            <FormControl><Checkbox checked={field.value} onCheckedChange={field.onChange} /></FormControl>
            <FormLabel className="!mt-0">{t("activities.allowSelfCancellation")}</FormLabel><FormMessage />
          </FormItem>
        )} />
        {allowSelfCancellation && (
          <FormField control={form.control} name="self_cancellation_deadline_hours" render={({ field }) => (
            <FormItem><FormLabel>{t("activities.selfCancellationHours")}</FormLabel><FormControl><Input type="number" min={0} {...field} /></FormControl><FormMessage /></FormItem>
          )} />
        )}
        <div className="flex gap-3">
          <Button type="submit" disabled={isPending}>
            {isPending ? t("common.loading") : t("common.save")}
          </Button>
          {onCancel && (
            <Button type="button" variant="outline" onClick={onCancel}>
              {t("common.cancel")}
            </Button>
          )}
        </div>
      </form>
    </Form>
  );
}
