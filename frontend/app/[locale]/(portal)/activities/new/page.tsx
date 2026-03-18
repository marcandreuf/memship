"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/lib/i18n/routing";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
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
import { useCreateActivity } from "@/features/activities/hooks/use-activities";

const activitySchema = z.object({
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
  allow_self_cancellation: z.boolean(),
  self_cancellation_deadline_hours: z.coerce.number().int().min(0).optional().or(z.literal("")),
}).refine((data) => new Date(data.ends_at) > new Date(data.starts_at), {
  message: "End date must be after start date",
  path: ["ends_at"],
}).refine((data) => new Date(data.registration_ends_at) > new Date(data.registration_starts_at), {
  message: "Registration close must be after registration open",
  path: ["registration_ends_at"],
}).refine((data) => new Date(data.registration_ends_at) <= new Date(data.starts_at), {
  message: "Registration must close before the activity starts",
  path: ["registration_ends_at"],
}).refine((data) => !data.min_age || !data.max_age || Number(data.max_age) >= Number(data.min_age), {
  message: "Max age must be greater than or equal to min age",
  path: ["max_age"],
}).refine((data) => data.max_participants >= data.min_participants, {
  message: "Max participants must be greater than or equal to min participants",
  path: ["max_participants"],
});

type ActivityFormValues = z.infer<typeof activitySchema>;

export default function NewActivityPage() {
  const t = useTranslations();
  const router = useRouter();
  const { mutateAsync: create, isPending } = useCreateActivity();
  const [apiError, setApiError] = useState<string | null>(null);

  const form = useForm<ActivityFormValues>({
    resolver: zodResolver(activitySchema),
    defaultValues: {
      name: "",
      short_description: "",
      description: "",
      starts_at: "",
      ends_at: "",
      registration_starts_at: "",
      registration_ends_at: "",
      location: "",
      location_details: "",
      location_url: "",
      min_participants: 0,
      max_participants: 1,
      min_age: "",
      max_age: "",
      allow_self_cancellation: false,
      self_cancellation_deadline_hours: "",
    },
  });

  const allowSelfCancellation = form.watch("allow_self_cancellation");

  async function onSubmit(data: ActivityFormValues) {
    const payload: Record<string, unknown> = {
      name: data.name,
      starts_at: new Date(data.starts_at).toISOString(),
      ends_at: new Date(data.ends_at).toISOString(),
      registration_starts_at: new Date(data.registration_starts_at).toISOString(),
      registration_ends_at: new Date(data.registration_ends_at).toISOString(),
      min_participants: data.min_participants,
      max_participants: data.max_participants,
      allow_self_cancellation: data.allow_self_cancellation,
    };
    if (data.short_description) payload.short_description = data.short_description;
    if (data.description) payload.description = data.description;
    if (data.location) payload.location = data.location;
    if (data.location_details) payload.location_details = data.location_details;
    if (data.location_url) payload.location_url = data.location_url;
    if (data.min_age !== "" && data.min_age !== undefined) payload.min_age = Number(data.min_age);
    if (data.max_age !== "" && data.max_age !== undefined) payload.max_age = Number(data.max_age);
    if (data.allow_self_cancellation && data.self_cancellation_deadline_hours !== "" && data.self_cancellation_deadline_hours !== undefined) {
      payload.self_cancellation_deadline_hours = Number(data.self_cancellation_deadline_hours);
    }

    try {
      setApiError(null);
      const result = await create(payload);
      router.push(`/activities/${result.id}`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "An error occurred";
      setApiError(message);
    }
  }

  return (
    <div className="space-y-4">
      <Button variant="outline" onClick={() => router.push("/activities")}>
        {t("common.back")}
      </Button>

      <h1 className="text-2xl font-bold">{t("activities.createActivity")}</h1>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          {/* Card 1: Basic Info */}
          <Card>
            <CardHeader>
              <CardTitle>{t("activities.basicInfo")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-5">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("activities.name")}</FormLabel>
                      <FormControl><Input {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="short_description"
                  render={({ field }) => (
                    <FormItem className="sm:col-span-4">
                      <FormLabel>{t("activities.shortDescription")}</FormLabel>
                      <FormControl><Input {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("activities.description")}</FormLabel>
                    <FormControl><Textarea rows={4} {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </CardContent>
          </Card>

          {/* Card 2: Schedule */}
          <Card>
            <CardHeader>
              <CardTitle>{t("activities.schedule")}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="starts_at"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("activities.startsAt")}</FormLabel>
                    <FormControl><Input type="datetime-local" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="ends_at"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("activities.endsAt")}</FormLabel>
                    <FormControl><Input type="datetime-local" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="registration_starts_at"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("activities.registrationStartsAt")}</FormLabel>
                    <FormControl><Input type="datetime-local" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="registration_ends_at"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("activities.registrationEndsAt")}</FormLabel>
                    <FormControl><Input type="datetime-local" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </CardContent>
          </Card>

          {/* Card 3: Location */}
          <Card>
            <CardHeader>
              <CardTitle>{t("activities.location")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-5">
                <FormField
                  control={form.control}
                  name="location"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("activities.location")}</FormLabel>
                      <FormControl><Input {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="location_details"
                  render={({ field }) => (
                    <FormItem className="sm:col-span-4">
                      <FormLabel>{t("activities.locationDetails")}</FormLabel>
                      <FormControl><Input {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={form.control}
                name="location_url"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("activities.locationUrl")}</FormLabel>
                    <FormControl><Input {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </CardContent>
          </Card>

          {/* Card 4: Capacity & Eligibility */}
          <Card>
            <CardHeader>
              <CardTitle>{t("activities.capacityEligibility")}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="min_participants"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("activities.minParticipants")}</FormLabel>
                    <FormControl><Input type="number" min={0} {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="max_participants"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("activities.maxParticipants")}</FormLabel>
                    <FormControl><Input type="number" min={1} {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="min_age"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("activities.minAge")}</FormLabel>
                    <FormControl><Input type="number" min={0} {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="max_age"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("activities.maxAge")}</FormLabel>
                    <FormControl><Input type="number" min={0} {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </CardContent>
          </Card>

          {/* Card 5: Options */}
          <Card>
            <CardHeader>
              <CardTitle>{t("activities.options")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <FormField
                control={form.control}
                name="allow_self_cancellation"
                render={({ field }) => (
                  <FormItem className="flex items-center gap-2">
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                    <FormLabel className="!mt-0">{t("activities.allowSelfCancellation")}</FormLabel>
                    <FormMessage />
                  </FormItem>
                )}
              />
              {allowSelfCancellation && (
                <FormField
                  control={form.control}
                  name="self_cancellation_deadline_hours"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("activities.selfCancellationHours")}</FormLabel>
                      <FormControl><Input type="number" min={0} {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}
            </CardContent>
          </Card>

          {apiError && (
            <p className="text-sm text-destructive">{apiError}</p>
          )}
          <Button type="submit" disabled={isPending}>
            {isPending ? t("common.loading") : t("common.create")}
          </Button>
        </form>
      </Form>
    </div>
  );
}
