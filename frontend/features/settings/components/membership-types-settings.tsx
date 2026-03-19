"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useMembershipTypes, useUpdateMembershipType, useDeleteMembershipType } from "@/features/members/hooks/use-members";
import { createMembershipType } from "@/features/members/services/members-api";
import type { MembershipTypeData } from "@/features/members/services/members-api";
import { useGroups } from "@/features/groups/hooks/use-groups";
import { useQueryClient } from "@tanstack/react-query";

const createSchema = z.object({
  name: z.string().min(1).max(255),
  slug: z.string().min(1).max(100).regex(/^[a-z0-9-]+$/),
  description: z.string().optional(),
  base_price: z.coerce.number().min(0),
  group_id: z.coerce.number().optional(),
});

type CreateFormValues = z.infer<typeof createSchema>;

export function MembershipTypesSettings() {
  const t = useTranslations();
  const { data: types, isLoading } = useMembershipTypes();
  const { data: groups } = useGroups();
  const updateMutation = useUpdateMembershipType();
  const deleteMutation = useDeleteMembershipType();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<MembershipTypeData | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<CreateFormValues>({
    resolver: zodResolver(createSchema),
    defaultValues: { name: "", slug: "", description: "", base_price: 0 },
  });

  function openCreate() {
    setEditing(null);
    form.reset({ name: "", slug: "", description: "", base_price: 0 });
    setOpen(true);
  }

  function openEdit(type: MembershipTypeData) {
    setEditing(type);
    form.reset({
      name: type.name,
      slug: type.slug,
      description: type.description || "",
      base_price: type.base_price,
      group_id: type.group_id || undefined,
    });
    setOpen(true);
  }

  async function onSubmit(data: CreateFormValues) {
    setIsSubmitting(true);
    try {
      const payload = {
        ...data,
        group_id: data.group_id || undefined,
      };
      if (editing) {
        await updateMutation.mutateAsync({ id: editing.id, data: payload });
      } else {
        await createMembershipType(payload);
        queryClient.invalidateQueries({ queryKey: ["membership-types"] });
      }
      setOpen(false);
      form.reset();
      setEditing(null);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDelete(id: number) {
    if (window.confirm(t("members.confirmDelete"))) {
      await deleteMutation.mutateAsync(id);
    }
  }

  if (isLoading) {
    return <div className="py-4 text-center text-muted-foreground">{t("common.loading")}</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">{t("members.typesInfo")}</p>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button size="sm" onClick={openCreate}>{t("members.createType")}</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editing ? t("common.edit") : t("members.createType")}
              </DialogTitle>
            </DialogHeader>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("members.typeName")}</FormLabel>
                      <FormControl><Input {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                {!editing && (
                  <FormField
                    control={form.control}
                    name="slug"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t("members.typeSlug")}</FormLabel>
                        <FormControl><Input {...field} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                )}
                <FormField
                  control={form.control}
                  name="description"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("members.typeDescription")}</FormLabel>
                      <FormControl><Input {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="base_price"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("members.typePrice")}</FormLabel>
                      <FormControl><Input type="number" step="0.01" {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="group_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("members.group")}</FormLabel>
                      <Select
                        onValueChange={(value) => field.onChange(value ? Number(value) : undefined)}
                        value={field.value ? String(field.value) : ""}
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder={t("members.noGroup")} />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {groups?.map((group) => (
                            <SelectItem key={group.id} value={String(group.id)}>
                              {group.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <Button type="submit" disabled={isSubmitting} className="w-full">
                  {isSubmitting ? t("common.loading") : editing ? t("common.save") : t("common.create")}
                </Button>
              </form>
            </Form>
          </DialogContent>
        </Dialog>
      </div>

      {!types?.length ? (
        <div className="py-4 text-center text-muted-foreground">{t("common.noResults")}</div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("members.typeName")}</TableHead>
              <TableHead>{t("members.typeSlug")}</TableHead>
              <TableHead>{t("members.typePrice")}</TableHead>
              <TableHead>{t("members.group")}</TableHead>
              <TableHead>{t("common.status")}</TableHead>
              <TableHead>{t("common.actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {types.map((type) => (
              <TableRow key={type.id}>
                <TableCell className="font-medium">{type.name}</TableCell>
                <TableCell className="font-mono text-sm">{type.slug}</TableCell>
                <TableCell>{type.base_price.toFixed(2)} EUR</TableCell>
                <TableCell>{type.group_name || t("members.noGroup")}</TableCell>
                <TableCell>
                  <Badge variant={type.is_active ? "default" : "outline"}>
                    {type.is_active ? t("status.active") : t("members.inactive")}
                  </Badge>
                </TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => openEdit(type)}>
                      {t("common.edit")}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDelete(type.id)}
                      disabled={deleteMutation.isPending}
                    >
                      {t("common.delete")}
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
