"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  useCreateModality,
  useUpdateModality,
  useDeleteModality,
} from "../hooks/use-activities";
import type { ActivityData, ActivityModalityData } from "../services/activities-api";

const modalitySchema = z.object({
  name: z.string().min(1).max(255),
  description: z.string().max(2000).optional().or(z.literal("")),
  max_participants: z.coerce.number().int().min(0).optional().or(z.literal("")),
  registration_deadline: z.string().optional().or(z.literal("")),
  display_order: z.coerce.number().int().min(0),
});
type ModalityFormValues = z.infer<typeof modalitySchema>;

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

interface ModalitiesTabProps {
  activityId: number;
  modalities: ActivityModalityData[];
  activity: ActivityData;
}

export function ModalitiesTab({ activityId, modalities, activity }: ModalitiesTabProps) {
  const t = useTranslations();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ActivityModalityData | null>(null);

  return (
    <div className="space-y-4 table-compact">
      <div className="flex justify-end">
        <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) setEditing(null); }}>
          <DialogTrigger asChild>
            <Button variant="outline" size="sm" onClick={() => setEditing(null)}>
              {t("activities.modalities.create")}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editing ? t("activities.modalities.edit") : t("activities.modalities.create")}
              </DialogTitle>
            </DialogHeader>
            <ModalityForm
              activityId={activityId}
              modality={editing}
              onSuccess={() => { setOpen(false); setEditing(null); }}
            />
          </DialogContent>
        </Dialog>
      </div>

      {!modalities.length ? (
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
            {modalities.map((m) => (
              <ModalityRow
                key={m.id}
                activityId={activityId}
                modality={m}
                onEdit={() => { setEditing(m); setOpen(true); }}
              />
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

function ModalityForm({
  activityId,
  modality,
  onSuccess,
}: {
  activityId: number;
  modality: ActivityModalityData | null;
  onSuccess: () => void;
}) {
  const t = useTranslations();
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

    try {
      if (modality) {
        await updateMutation.mutateAsync({ modalityId: modality.id, data: payload });
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

function ModalityRow({
  activityId,
  modality,
  onEdit,
}: {
  activityId: number;
  modality: ActivityModalityData;
  onEdit: () => void;
}) {
  const t = useTranslations();
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
                try {
                  await deleteMutation.mutateAsync(modality.id);
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
