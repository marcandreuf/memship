"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
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
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { TabContentSkeleton } from "@/components/ui/skeletons";
import { toast } from "sonner";
import { mapApiErrorsToForm } from "@/lib/errors";
import {
  useContacts,
  useContactTypes,
  useCreateContact,
  useUpdateContact,
  useDeleteContact,
} from "../hooks/use-contacts";
import type { ContactData } from "../services/contacts-api";

const contactSchema = z.object({
  contact_type_id: z.string().optional(),
  value: z.string().min(1).max(255),
  label: z.string().max(100).optional().or(z.literal("")),
  is_primary: z.boolean(),
});
type ContactFormValues = z.infer<typeof contactSchema>;

interface ContactInfoTabProps {
  personId: number;
}

export function ContactInfoTab({ personId }: ContactInfoTabProps) {
  const t = useTranslations();
  const { data: contacts = [], isLoading } = useContacts(personId);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ContactData | null>(null);

  if (isLoading) return <TabContentSkeleton />;

  return (
    <div className="space-y-4 table-compact">
      <div className="flex justify-end">
        <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) setEditing(null); }}>
          <DialogTrigger asChild>
            <Button variant="outline" size="sm" onClick={() => setEditing(null)}>
              {t("members.addContact")}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editing ? t("members.editContact") : t("members.addContact")}
              </DialogTitle>
            </DialogHeader>
            <ContactForm
              personId={personId}
              contact={editing}
              onSuccess={() => { setOpen(false); setEditing(null); }}
            />
          </DialogContent>
        </Dialog>
      </div>

      {!contacts.length ? (
        <p className="text-sm text-muted-foreground">{t("members.noContacts")}</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("members.contactType")}</TableHead>
              <TableHead>{t("members.contactValue")}</TableHead>
              <TableHead>{t("members.contactLabel")}</TableHead>
              <TableHead>{t("common.actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {contacts.map((c) => (
              <ContactRow
                key={c.id}
                personId={personId}
                contact={c}
                onEdit={() => { setEditing(c); setOpen(true); }}
              />
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

function ContactForm({
  personId,
  contact,
  onSuccess,
}: {
  personId: number;
  contact: ContactData | null;
  onSuccess: () => void;
}) {
  const t = useTranslations();
  const createMutation = useCreateContact(personId);
  const updateMutation = useUpdateContact(personId);
  const { data: contactTypes = [] } = useContactTypes();

  const form = useForm<ContactFormValues>({
    resolver: zodResolver(contactSchema),
    defaultValues: {
      contact_type_id: contact?.contact_type_id?.toString() || "",
      value: contact?.value || "",
      label: contact?.label || "",
      is_primary: contact?.is_primary ?? false,
    },
  });

  // Default to Mobile Phone when types load and no type is set
  useEffect(() => {
    if (contactTypes.length > 0 && !form.getValues("contact_type_id")) {
      const mobile = contactTypes.find(ct => ct.code === "phone_mobile");
      if (mobile) form.setValue("contact_type_id", mobile.id.toString());
    }
  }, [contactTypes, form]);

  async function onSubmit(data: ContactFormValues) {
    const payload: Record<string, unknown> = {
      value: data.value,
      is_primary: data.is_primary,
    };
    if (data.contact_type_id) payload.contact_type_id = parseInt(data.contact_type_id);
    if (data.label) payload.label = data.label;

    try {
      if (contact) {
        await updateMutation.mutateAsync({ contactId: contact.id, data: payload });
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
        <FormField control={form.control} name="contact_type_id" render={({ field }) => (
          <FormItem>
            <FormLabel>{t("members.contactType")}</FormLabel>
            <Select onValueChange={field.onChange} value={field.value}>
              <FormControl><SelectTrigger><SelectValue placeholder={t("members.selectContactType")} /></SelectTrigger></FormControl>
              <SelectContent>
                {contactTypes.map((ct) => (
                  <SelectItem key={ct.id} value={ct.id.toString()}>{ct.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <FormMessage />
          </FormItem>
        )} />
        <FormField control={form.control} name="value" render={({ field }) => (
          <FormItem>
            <FormLabel>{t("members.contactValue")}</FormLabel>
            <FormControl><Input {...field} placeholder="+34 600 123 456" /></FormControl>
            <FormMessage />
          </FormItem>
        )} />
        <FormField control={form.control} name="label" render={({ field }) => (
          <FormItem>
            <FormLabel>{t("members.contactLabel")}</FormLabel>
            <FormControl><Input {...field} placeholder={t("members.contactLabelPlaceholder")} /></FormControl>
            <FormMessage />
          </FormItem>
        )} />
        <FormField control={form.control} name="is_primary" render={({ field }) => (
          <FormItem className="flex items-center gap-2">
            <FormControl><Checkbox checked={field.value} onCheckedChange={field.onChange} /></FormControl>
            <FormLabel className="!mt-0">{t("members.primaryContact")}</FormLabel>
            <FormMessage />
          </FormItem>
        )} />
        <Button type="submit" disabled={isPending} className="w-full">
          {isPending ? t("common.loading") : t("common.save")}
        </Button>
      </form>
    </Form>
  );
}

function ContactRow({
  personId,
  contact,
  onEdit,
}: {
  personId: number;
  contact: ContactData;
  onEdit: () => void;
}) {
  const t = useTranslations();
  const deleteMutation = useDeleteContact(personId);
  const [confirmDialog, confirmAction] = useConfirmDialog();

  return (
    <TableRow>
      <TableCell>
        {contact.contact_type_name || "—"}
        {contact.is_primary && (
          <Badge variant="default" className="ml-2">{t("members.primary")}</Badge>
        )}
      </TableCell>
      <TableCell className="font-mono text-sm">{contact.value}</TableCell>
      <TableCell>{contact.label || "—"}</TableCell>
      <TableCell>
        <div className="flex gap-2">
          {confirmDialog}
          <Button variant="outline" size="sm" onClick={onEdit}>{t("common.edit")}</Button>
          <Button
            variant="outline" size="sm"
            onClick={() => {
              confirmAction({
                title: t("members.deleteContactConfirm"),
                cancelLabel: t("common.cancel"),
                confirmLabel: t("common.delete"),
                onConfirm: async () => {
                  try {
                    await deleteMutation.mutateAsync(contact.id);
                    toast.success(t("toast.success.deleted"));
                  } catch { /* global handler */ }
                },
              });
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
