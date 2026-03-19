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
  useAttachmentTypes, useCreateAttachmentType, useUpdateAttachmentType, useDeleteAttachmentType,
} from "../hooks/use-activities";
import type { ActivityAttachmentTypeData } from "../services/activities-api";

const attachmentTypeSchema = z.object({
  name: z.string().min(1).max(255),
  description: z.string().optional().or(z.literal("")),
  allowed_extensions: z.string().optional().or(z.literal("")),
  max_file_size_mb: z.coerce.number().int().min(1).max(50),
  is_mandatory: z.boolean(),
  display_order: z.coerce.number().int().min(0),
});
type AttachmentTypeFormValues = z.infer<typeof attachmentTypeSchema>;

interface AttachmentTypesTabProps {
  activityId: number;
}

export function AttachmentTypesTab({ activityId }: AttachmentTypesTabProps) {
  const t = useTranslations();
  const { data: types = [], isLoading } = useAttachmentTypes(activityId);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ActivityAttachmentTypeData | null>(null);

  if (isLoading) return <p className="text-sm text-muted-foreground">{t("common.loading")}</p>;

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) setEditing(null); }}>
          <DialogTrigger asChild>
            <Button variant="outline" size="sm" onClick={() => setEditing(null)}>
              {t("activities.attachments.create")}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editing ? t("activities.attachments.edit") : t("activities.attachments.create")}
              </DialogTitle>
            </DialogHeader>
            <AttachmentTypeForm
              activityId={activityId}
              attachmentType={editing}
              onSuccess={() => { setOpen(false); setEditing(null); }}
            />
          </DialogContent>
        </Dialog>
      </div>

      {!types.length ? (
        <p className="text-sm text-muted-foreground">{t("activities.attachments.noAttachments")}</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("activities.attachments.name")}</TableHead>
              <TableHead>{t("activities.attachments.extensions")}</TableHead>
              <TableHead>{t("activities.attachments.maxSize")}</TableHead>
              <TableHead>{t("activities.attachments.mandatory")}</TableHead>
              <TableHead>{t("common.actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {types.map((at) => (
              <AttachmentTypeRow
                key={at.id}
                activityId={activityId}
                attachmentType={at}
                onEdit={() => { setEditing(at); setOpen(true); }}
              />
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

function AttachmentTypeForm({
  activityId, attachmentType, onSuccess,
}: {
  activityId: number;
  attachmentType: ActivityAttachmentTypeData | null;
  onSuccess: () => void;
}) {
  const t = useTranslations();
  const createMutation = useCreateAttachmentType(activityId);
  const updateMutation = useUpdateAttachmentType(activityId);

  const form = useForm<AttachmentTypeFormValues>({
    resolver: zodResolver(attachmentTypeSchema),
    defaultValues: {
      name: attachmentType?.name || "",
      description: attachmentType?.description || "",
      allowed_extensions: attachmentType?.allowed_extensions?.join(", ") || "",
      max_file_size_mb: attachmentType?.max_file_size_mb ?? 5,
      is_mandatory: attachmentType?.is_mandatory ?? true,
      display_order: attachmentType?.display_order ?? 1,
    },
  });

  async function onSubmit(data: AttachmentTypeFormValues) {
    const payload: Record<string, unknown> = {
      name: data.name,
      max_file_size_mb: data.max_file_size_mb,
      is_mandatory: data.is_mandatory,
      display_order: data.display_order,
    };
    if (data.description) payload.description = data.description;
    if (data.allowed_extensions) {
      payload.allowed_extensions = data.allowed_extensions.split(",").map((e) => e.trim().toLowerCase()).filter(Boolean);
    } else {
      payload.allowed_extensions = [];
    }

    if (attachmentType) {
      await updateMutation.mutateAsync({ typeId: attachmentType.id, data: payload });
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
          <FormItem><FormLabel>{t("activities.attachments.name")}</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <FormField control={form.control} name="description" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.description")}</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <FormField control={form.control} name="allowed_extensions" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.attachments.extensions")}</FormLabel><FormControl><Input placeholder="pdf, jpg, png" {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <FormField control={form.control} name="max_file_size_mb" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.attachments.maxSize")}</FormLabel><FormControl><Input type="number" min={1} max={50} {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <FormField control={form.control} name="is_mandatory" render={({ field }) => (
          <FormItem className="flex items-center gap-2">
            <FormControl><Checkbox checked={field.value} onCheckedChange={field.onChange} /></FormControl>
            <FormLabel className="!mt-0">{t("activities.attachments.mandatory")}</FormLabel><FormMessage />
          </FormItem>
        )} />
        <Button type="submit" disabled={isPending} className="w-full">
          {isPending ? t("common.loading") : t("common.save")}
        </Button>
      </form>
    </Form>
  );
}

function AttachmentTypeRow({
  activityId, attachmentType, onEdit,
}: {
  activityId: number;
  attachmentType: ActivityAttachmentTypeData;
  onEdit: () => void;
}) {
  const t = useTranslations();
  const deleteMutation = useDeleteAttachmentType(activityId);

  return (
    <TableRow>
      <TableCell className="font-medium">{attachmentType.name}</TableCell>
      <TableCell>{attachmentType.allowed_extensions?.length ? attachmentType.allowed_extensions.join(", ") : t("activities.attachments.anyFile")}</TableCell>
      <TableCell>{attachmentType.max_file_size_mb} MB</TableCell>
      <TableCell>
        <Badge variant={attachmentType.is_mandatory ? "default" : "secondary"}>
          {attachmentType.is_mandatory ? t("activities.attachments.mandatory") : t("activities.consents.optional")}
        </Badge>
      </TableCell>
      <TableCell>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onEdit}>{t("common.edit")}</Button>
          <Button
            variant="outline" size="sm"
            onClick={async () => {
              if (confirm(t("activities.actions.confirmDelete"))) {
                await deleteMutation.mutateAsync(attachmentType.id);
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
