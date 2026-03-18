"use client";

import { use, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/lib/i18n/routing";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { useAuth } from "@/features/auth/hooks/use-auth";
import {
  useActivity,
  useUpdateActivity,
  useDeleteActivity,
  usePublishActivity,
  useArchiveActivity,
  useCancelActivity,
  useCreateModality,
  useUpdateModality,
  useDeleteModality,
  useCreatePrice,
  useUpdatePrice,
  useDeletePrice,
} from "@/features/activities/hooks/use-activities";
import type {
  ActivityData,
  ActivityModalityData,
  ActivityPriceData,
} from "@/features/activities/services/activities-api";

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  draft: "outline",
  published: "default",
  archived: "secondary",
  cancelled: "destructive",
  completed: "secondary",
};

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

// --- Modality dialog schema ---
const modalitySchema = z.object({
  name: z.string().min(1).max(255),
  description: z.string().optional().or(z.literal("")),
  max_participants: z.coerce.number().int().min(0).optional().or(z.literal("")),
  registration_deadline: z.string().optional().or(z.literal("")),
  display_order: z.coerce.number().int().min(0),
});
type ModalityFormValues = z.infer<typeof modalitySchema>;

// --- Price dialog schema ---
const priceSchema = z.object({
  name: z.string().min(1).max(255),
  description: z.string().optional().or(z.literal("")),
  amount: z.coerce.number().min(0),
  modality_id: z.coerce.number().int().optional().or(z.literal("")),
  display_order: z.coerce.number().int().min(0),
  is_optional: z.boolean(),
  is_default: z.boolean(),
  valid_from: z.string().optional().or(z.literal("")),
  valid_until: z.string().optional().or(z.literal("")),
});
type PriceFormValues = z.infer<typeof priceSchema>;

// --- Edit activity schema ---
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

// --- Field display ---
function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value || "—"}</dd>
    </div>
  );
}

export default function ActivityDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const activityId = Number(id);
  const t = useTranslations();
  const router = useRouter();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin" || user?.role === "super_admin";

  const { data: activity, isLoading } = useActivity(activityId);
  const updateMutation = useUpdateActivity();
  const deleteMutation = useDeleteActivity();
  const publishMutation = usePublishActivity();
  const archiveMutation = useArchiveActivity();
  const cancelMutation = useCancelActivity();

  const [editOpen, setEditOpen] = useState(false);
  const [modalityOpen, setModalityOpen] = useState(false);
  const [editingModality, setEditingModality] = useState<ActivityModalityData | null>(null);
  const [priceOpen, setPriceOpen] = useState(false);
  const [editingPrice, setEditingPrice] = useState<ActivityPriceData | null>(null);

  if (isLoading) {
    return <div className="py-8 text-center text-muted-foreground">{t("common.loading")}</div>;
  }

  if (!activity) {
    return <div className="py-8 text-center text-muted-foreground">{t("common.noResults")}</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={() => router.push("/activities")}>
            {t("common.back")}
          </Button>
          <h1 className="text-xl font-bold">{activity.name}</h1>
          <Badge variant={STATUS_VARIANTS[activity.status] || "outline"}>
            {t(`activities.status.${activity.status}`)}
          </Badge>
        </div>
        {isAdmin && (
          <div className="flex gap-2">
            {activity.status === "draft" && (
              <Button
                onClick={async () => {
                  if (confirm(t("activities.actions.confirmPublish"))) {
                    await publishMutation.mutateAsync(activityId);
                  }
                }}
                disabled={publishMutation.isPending}
              >
                {t("activities.actions.publish")}
              </Button>
            )}
            {activity.status === "published" && (
              <Button
                variant="secondary"
                onClick={async () => {
                  if (confirm(t("activities.actions.confirmArchive"))) {
                    await archiveMutation.mutateAsync(activityId);
                  }
                }}
                disabled={archiveMutation.isPending}
              >
                {t("activities.actions.archive")}
              </Button>
            )}
            {(activity.status === "draft" || activity.status === "published") && (
              <Button
                variant="destructive"
                onClick={async () => {
                  if (confirm(t("activities.actions.confirmCancel"))) {
                    await cancelMutation.mutateAsync(activityId);
                  }
                }}
                disabled={cancelMutation.isPending}
              >
                {t("activities.actions.cancel")}
              </Button>
            )}
            {activity.status === "draft" && (
              <Button
                variant="destructive"
                onClick={async () => {
                  if (confirm(t("activities.actions.confirmDelete"))) {
                    await deleteMutation.mutateAsync(activityId);
                    router.push("/activities");
                  }
                }}
                disabled={deleteMutation.isPending}
              >
                {t("common.delete")}
              </Button>
            )}
          </div>
        )}
      </div>

      {/* Section 1: Activity Details */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>{t("activities.basicInfo")}</CardTitle>
          {isAdmin && (
            <Dialog open={editOpen} onOpenChange={setEditOpen}>
              <DialogTrigger asChild>
                <Button variant="outline" size="sm">{t("common.edit")}</Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>{t("activities.editActivity")}</DialogTitle>
                </DialogHeader>
                <EditActivityForm
                  activity={activity}
                  onSubmit={async (data) => {
                    await updateMutation.mutateAsync({ id: activityId, data });
                    setEditOpen(false);
                  }}
                  isPending={updateMutation.isPending}
                  t={t}
                />
              </DialogContent>
            </Dialog>
          )}
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Field label={t("activities.name")} value={activity.name} />
            <Field label={t("activities.slug")} value={activity.slug} />
            <Field label={t("activities.shortDescription")} value={activity.short_description} />
            <Field label={t("activities.startsAt")} value={formatDate(activity.starts_at)} />
            <Field label={t("activities.endsAt")} value={formatDate(activity.ends_at)} />
            <Field label={t("activities.registrationStartsAt")} value={formatDate(activity.registration_starts_at)} />
            <Field label={t("activities.registrationEndsAt")} value={formatDate(activity.registration_ends_at)} />
            <Field label={t("activities.location")} value={activity.location} />
            <Field label={t("activities.locationDetails")} value={activity.location_details} />
            <Field label={t("activities.minParticipants")} value={activity.min_participants} />
            <Field label={t("activities.maxParticipants")} value={activity.max_participants} />
            <Field label={t("activities.capacity")} value={`${activity.current_participants}/${activity.max_participants}`} />
            <Field label={t("activities.minAge")} value={activity.min_age} />
            <Field label={t("activities.maxAge")} value={activity.max_age} />
            <Field label={t("activities.taxRate")} value={`${activity.tax_rate}%`} />
            <Field label={t("activities.allowSelfCancellation")} value={activity.allow_self_cancellation ? t("common.yes") : t("common.no")} />
          </dl>
          {activity.description && (
            <div className="mt-4">
              <dt className="text-sm text-muted-foreground">{t("activities.description")}</dt>
              <dd className="mt-1 whitespace-pre-wrap">{activity.description}</dd>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Section 2: Modalities */}
      {isAdmin && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>{t("activities.modalities.title")}</CardTitle>
            <Dialog open={modalityOpen} onOpenChange={(open) => { setModalityOpen(open); if (!open) setEditingModality(null); }}>
              <DialogTrigger asChild>
                <Button variant="outline" size="sm" onClick={() => setEditingModality(null)}>
                  {t("activities.modalities.create")}
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>
                    {editingModality ? t("activities.modalities.edit") : t("activities.modalities.create")}
                  </DialogTitle>
                </DialogHeader>
                <ModalityForm
                  activityId={activityId}
                  modality={editingModality}
                  onSuccess={() => { setModalityOpen(false); setEditingModality(null); }}
                  t={t}
                />
              </DialogContent>
            </Dialog>
          </CardHeader>
          <CardContent>
            {!activity.modalities.length ? (
              <p className="text-sm text-muted-foreground">{t("activities.modalities.noModalities")}</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("activities.modalities.name")}</TableHead>
                    <TableHead>{t("activities.modalities.maxParticipants")}</TableHead>
                    <TableHead>{t("activities.modalities.currentParticipants")}</TableHead>
                    <TableHead>{t("activities.modalities.deadline")}</TableHead>
                    <TableHead>{t("common.actions")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {activity.modalities.map((m) => (
                    <ModalityRow
                      key={m.id}
                      activityId={activityId}
                      modality={m}
                      onEdit={() => { setEditingModality(m); setModalityOpen(true); }}
                      t={t}
                    />
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {/* Section 3: Prices */}
      {isAdmin && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>{t("activities.prices.title")}</CardTitle>
            <Dialog open={priceOpen} onOpenChange={(open) => { setPriceOpen(open); if (!open) setEditingPrice(null); }}>
              <DialogTrigger asChild>
                <Button variant="outline" size="sm" onClick={() => setEditingPrice(null)}>
                  {t("activities.prices.create")}
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>
                    {editingPrice ? t("activities.prices.edit") : t("activities.prices.create")}
                  </DialogTitle>
                </DialogHeader>
                <PriceForm
                  activityId={activityId}
                  modalities={activity.modalities}
                  price={editingPrice}
                  onSuccess={() => { setPriceOpen(false); setEditingPrice(null); }}
                  t={t}
                />
              </DialogContent>
            </Dialog>
          </CardHeader>
          <CardContent>
            {!activity.prices.length ? (
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
                  {activity.prices.map((p) => (
                    <PriceRow
                      key={p.id}
                      activityId={activityId}
                      modalities={activity.modalities}
                      price={p}
                      onEdit={() => { setEditingPrice(p); setPriceOpen(true); }}
                      t={t}
                    />
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {/* Member view: Prices summary */}
      {!isAdmin && activity.prices.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>{t("activities.prices.title")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {activity.prices.filter(p => p.is_visible).map((p) => (
                <div key={p.id} className="flex justify-between">
                  <span>{p.name}</span>
                  <span className="font-medium">{formatAmount(p.amount) || t("activities.prices.free")}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// --- Edit Activity Form ---
function EditActivityForm({
  activity,
  onSubmit,
  isPending,
  t,
}: {
  activity: ActivityData;
  onSubmit: (data: Record<string, unknown>) => Promise<void>;
  isPending: boolean;
  t: ReturnType<typeof useTranslations>;
}) {
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
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
        <FormField control={form.control} name="name" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.name")}</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <FormField control={form.control} name="short_description" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.shortDescription")}</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <FormField control={form.control} name="description" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.description")}</FormLabel><FormControl><Textarea rows={3} {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <div className="grid gap-4 sm:grid-cols-2">
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
        <FormField control={form.control} name="location" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.location")}</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <FormField control={form.control} name="location_details" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.locationDetails")}</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <FormField control={form.control} name="location_url" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.locationUrl")}</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField control={form.control} name="min_participants" render={({ field }) => (
            <FormItem><FormLabel>{t("activities.minParticipants")}</FormLabel><FormControl><Input type="number" min={0} {...field} /></FormControl><FormMessage /></FormItem>
          )} />
          <FormField control={form.control} name="max_participants" render={({ field }) => (
            <FormItem><FormLabel>{t("activities.maxParticipants")}</FormLabel><FormControl><Input type="number" min={1} {...field} /></FormControl><FormMessage /></FormItem>
          )} />
          <FormField control={form.control} name="min_age" render={({ field }) => (
            <FormItem><FormLabel>{t("activities.minAge")}</FormLabel><FormControl><Input type="number" min={0} {...field} /></FormControl><FormMessage /></FormItem>
          )} />
          <FormField control={form.control} name="max_age" render={({ field }) => (
            <FormItem><FormLabel>{t("activities.maxAge")}</FormLabel><FormControl><Input type="number" min={0} {...field} /></FormControl><FormMessage /></FormItem>
          )} />
          <FormField control={form.control} name="tax_rate" render={({ field }) => (
            <FormItem><FormLabel>{t("activities.taxRate")}</FormLabel><FormControl><Input type="number" min={0} max={100} step="0.01" {...field} /></FormControl><FormMessage /></FormItem>
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
        <Button type="submit" disabled={isPending} className="w-full">
          {isPending ? t("common.loading") : t("common.save")}
        </Button>
      </form>
    </Form>
  );
}

// --- Modality Form ---
function ModalityForm({
  activityId,
  modality,
  onSuccess,
  t,
}: {
  activityId: number;
  modality: ActivityModalityData | null;
  onSuccess: () => void;
  t: ReturnType<typeof useTranslations>;
}) {
  const createMutation = useCreateModality(activityId);
  const updateMutation = useUpdateModality(activityId);

  const form = useForm<ModalityFormValues>({
    resolver: zodResolver(modalitySchema),
    defaultValues: {
      name: modality?.name || "",
      description: modality?.description || "",
      max_participants: modality?.max_participants ?? "",
      registration_deadline: modality?.registration_deadline ? toLocalDatetime(modality.registration_deadline) : "",
      display_order: modality?.display_order ?? 1,
    },
  });

  async function onSubmit(data: ModalityFormValues) {
    const payload: Record<string, unknown> = {
      name: data.name,
      display_order: data.display_order,
    };
    if (data.description) payload.description = data.description;
    if (data.max_participants !== "" && data.max_participants !== undefined) payload.max_participants = Number(data.max_participants);
    if (data.registration_deadline) payload.registration_deadline = new Date(data.registration_deadline).toISOString();

    if (modality) {
      await updateMutation.mutateAsync({ modalityId: modality.id, data: payload });
    } else {
      await createMutation.mutateAsync(payload);
    }
    onSuccess();
  }

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField control={form.control} name="name" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.modalities.name")}</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <FormField control={form.control} name="description" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.modalities.description")}</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <FormField control={form.control} name="max_participants" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.modalities.maxParticipants")}</FormLabel><FormControl><Input type="number" min={0} {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <FormField control={form.control} name="registration_deadline" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.modalities.deadline")}</FormLabel><FormControl><Input type="datetime-local" {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <Button type="submit" disabled={isPending} className="w-full">
          {isPending ? t("common.loading") : t("common.save")}
        </Button>
      </form>
    </Form>
  );
}

// --- Modality Row ---
function ModalityRow({
  activityId,
  modality,
  onEdit,
  t,
}: {
  activityId: number;
  modality: ActivityModalityData;
  onEdit: () => void;
  t: ReturnType<typeof useTranslations>;
}) {
  const deleteMutation = useDeleteModality(activityId);

  return (
    <TableRow>
      <TableCell className="font-medium">{modality.name}</TableCell>
      <TableCell>{modality.max_participants ?? "—"}</TableCell>
      <TableCell>{modality.current_participants}</TableCell>
      <TableCell>{modality.registration_deadline ? formatDate(modality.registration_deadline) : "—"}</TableCell>
      <TableCell>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onEdit}>{t("common.edit")}</Button>
          <Button
            variant="outline"
            size="sm"
            onClick={async () => {
              if (confirm(t("activities.actions.confirmDelete"))) {
                await deleteMutation.mutateAsync(modality.id);
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

// --- Price Form ---
function PriceForm({
  activityId,
  modalities,
  price,
  onSuccess,
  t,
}: {
  activityId: number;
  modalities: ActivityModalityData[];
  price: ActivityPriceData | null;
  onSuccess: () => void;
  t: ReturnType<typeof useTranslations>;
}) {
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

    if (price) {
      await updateMutation.mutateAsync({ priceId: price.id, data: payload });
    } else {
      await createMutation.mutateAsync(payload);
    }
    onSuccess();
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

// --- Price Row ---
function PriceRow({
  activityId,
  modalities,
  price,
  onEdit,
  t,
}: {
  activityId: number;
  modalities: ActivityModalityData[];
  price: ActivityPriceData;
  onEdit: () => void;
  t: ReturnType<typeof useTranslations>;
}) {
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
                await deleteMutation.mutateAsync(price.id);
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
