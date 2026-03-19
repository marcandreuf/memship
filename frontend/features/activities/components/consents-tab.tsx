"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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
  useConsents, useCreateConsent, useUpdateConsent, useDeleteConsent,
} from "../hooks/use-activities";
import type { ActivityConsentData } from "../services/activities-api";

const consentSchema = z.object({
  title: z.string().min(1).max(255),
  content: z.string().min(1),
  is_mandatory: z.boolean(),
  display_order: z.coerce.number().int().min(0),
});
type ConsentFormValues = z.infer<typeof consentSchema>;

interface ConsentsTabProps {
  activityId: number;
}

export function ConsentsTab({ activityId }: ConsentsTabProps) {
  const t = useTranslations();
  const { data: consents = [], isLoading } = useConsents(activityId);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ActivityConsentData | null>(null);

  if (isLoading) return <p className="text-sm text-muted-foreground">{t("common.loading")}</p>;

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) setEditing(null); }}>
          <DialogTrigger asChild>
            <Button variant="outline" size="sm" onClick={() => setEditing(null)}>
              {t("activities.consents.create")}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editing ? t("activities.consents.edit") : t("activities.consents.create")}
              </DialogTitle>
            </DialogHeader>
            <ConsentForm
              activityId={activityId}
              consent={editing}
              onSuccess={() => { setOpen(false); setEditing(null); }}
            />
          </DialogContent>
        </Dialog>
      </div>

      {!consents.length ? (
        <p className="text-sm text-muted-foreground">{t("activities.consents.noConsents")}</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("activities.consents.consentTitle")}</TableHead>
              <TableHead>{t("activities.consents.mandatory")}</TableHead>
              <TableHead>{t("activities.consents.order")}</TableHead>
              <TableHead>{t("common.actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {consents.map((c) => (
              <ConsentRow
                key={c.id}
                activityId={activityId}
                consent={c}
                onEdit={() => { setEditing(c); setOpen(true); }}
              />
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

function ConsentForm({
  activityId, consent, onSuccess,
}: {
  activityId: number;
  consent: ActivityConsentData | null;
  onSuccess: () => void;
}) {
  const t = useTranslations();
  const createMutation = useCreateConsent(activityId);
  const updateMutation = useUpdateConsent(activityId);

  const form = useForm<ConsentFormValues>({
    resolver: zodResolver(consentSchema),
    defaultValues: {
      title: consent?.title || "",
      content: consent?.content || "",
      is_mandatory: consent?.is_mandatory ?? true,
      display_order: consent?.display_order ?? 1,
    },
  });

  async function onSubmit(data: ConsentFormValues) {
    if (consent) {
      await updateMutation.mutateAsync({ consentId: consent.id, data });
    } else {
      await createMutation.mutateAsync(data);
    }
    onSuccess();
  }

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField control={form.control} name="title" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.consents.consentTitle")}</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <FormField control={form.control} name="content" render={({ field }) => (
          <FormItem><FormLabel>{t("activities.consents.content")}</FormLabel><FormControl><Textarea rows={4} {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        <FormField control={form.control} name="is_mandatory" render={({ field }) => (
          <FormItem className="flex items-center gap-2">
            <FormControl><Checkbox checked={field.value} onCheckedChange={field.onChange} /></FormControl>
            <FormLabel className="!mt-0">{t("activities.consents.mandatory")}</FormLabel><FormMessage />
          </FormItem>
        )} />
        <Button type="submit" disabled={isPending} className="w-full">
          {isPending ? t("common.loading") : t("common.save")}
        </Button>
      </form>
    </Form>
  );
}

function ConsentRow({
  activityId, consent, onEdit,
}: {
  activityId: number;
  consent: ActivityConsentData;
  onEdit: () => void;
}) {
  const t = useTranslations();
  const deleteMutation = useDeleteConsent(activityId);

  return (
    <TableRow>
      <TableCell className="font-medium">{consent.title}</TableCell>
      <TableCell>
        <Badge variant={consent.is_mandatory ? "default" : "secondary"}>
          {consent.is_mandatory ? t("activities.consents.mandatory") : t("activities.consents.optional")}
        </Badge>
      </TableCell>
      <TableCell>{consent.display_order}</TableCell>
      <TableCell>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onEdit}>{t("common.edit")}</Button>
          <Button
            variant="outline" size="sm"
            onClick={async () => {
              if (confirm(t("activities.actions.confirmDelete"))) {
                await deleteMutation.mutateAsync(consent.id);
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
