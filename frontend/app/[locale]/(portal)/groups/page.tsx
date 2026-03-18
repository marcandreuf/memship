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
  Card,
  CardContent,
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
import { PageInfo } from "@/components/page-info";
import { useGroups, useCreateGroup, useUpdateGroup, useDeleteGroup } from "@/features/groups/hooks/use-groups";
import type { GroupData } from "@/features/groups/services/groups-api";

const groupSchema = z.object({
  name: z.string().min(1).max(255),
  slug: z.string().min(1).max(100).regex(/^[a-z0-9-]+$/),
  description: z.string().optional(),
  is_billable: z.boolean().optional(),
  color: z.string().regex(/^#[0-9a-fA-F]{6}$/).optional().or(z.literal("")),
});

type GroupFormValues = z.infer<typeof groupSchema>;

export default function GroupsPage() {
  const t = useTranslations();
  const { data: groups, isLoading } = useGroups();
  const createMutation = useCreateGroup();
  const updateMutation = useUpdateGroup();
  const deleteMutation = useDeleteGroup();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<GroupData | null>(null);

  const form = useForm<GroupFormValues>({
    resolver: zodResolver(groupSchema),
    defaultValues: { name: "", slug: "", description: "", is_billable: true, color: "" },
  });

  function openCreate() {
    setEditing(null);
    form.reset({ name: "", slug: "", description: "", is_billable: true, color: "" });
    setOpen(true);
  }

  function openEdit(group: GroupData) {
    setEditing(group);
    form.reset({
      name: group.name,
      slug: group.slug,
      description: group.description || "",
      is_billable: group.is_billable,
      color: group.color || "",
    });
    setOpen(true);
  }

  async function onSubmit(data: GroupFormValues) {
    const payload = {
      ...data,
      color: data.color || undefined,
    };
    if (editing) {
      await updateMutation.mutateAsync({ id: editing.id, data: payload });
    } else {
      await createMutation.mutateAsync(payload);
    }
    setOpen(false);
    form.reset();
  }

  async function handleDelete(id: number) {
    if (window.confirm(t("groups.deleteConfirm"))) {
      await deleteMutation.mutateAsync(id);
    }
  }

  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold">{t("groups.title")}</h1>
          <PageInfo text={t("groups.info")} />
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button onClick={openCreate}>{t("groups.createGroup")}</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editing ? t("groups.editGroup") : t("groups.createGroup")}
              </DialogTitle>
            </DialogHeader>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("groups.name")}</FormLabel>
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
                        <FormLabel>{t("groups.slug")}</FormLabel>
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
                      <FormLabel>{t("groups.description")}</FormLabel>
                      <FormControl><Input {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="color"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("groups.color")}</FormLabel>
                      <FormControl>
                        <div className="flex gap-2">
                          <Input type="color" className="w-12 h-10 p-1" value={field.value || "#000000"} onChange={(e) => field.onChange(e.target.value)} />
                          <Input {...field} placeholder="#FF6B6B" className="flex-1" />
                        </div>
                      </FormControl>
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

      {isLoading ? (
        <div className="py-8 text-center text-muted-foreground">{t("common.loading")}</div>
      ) : !groups?.length ? (
        <div className="py-8 text-center text-muted-foreground">{t("groups.noGroups")}</div>
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("groups.name")}</TableHead>
                  <TableHead>{t("groups.slug")}</TableHead>
                  <TableHead>{t("groups.billable")}</TableHead>
                  <TableHead>{t("groups.color")}</TableHead>
                  <TableHead>{t("common.actions")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {groups.map((group) => (
                  <TableRow key={group.id}>
                    <TableCell className="font-medium">{group.name}</TableCell>
                    <TableCell className="font-mono text-sm">{group.slug}</TableCell>
                    <TableCell>
                      <Badge variant={group.is_billable ? "default" : "outline"}>
                        {group.is_billable ? t("common.yes") : t("common.no")}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {group.color && (
                        <div className="flex items-center gap-2">
                          <div
                            className="h-4 w-4 rounded-full border"
                            style={{ backgroundColor: group.color }}
                          />
                          <span className="font-mono text-xs">{group.color}</span>
                        </div>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={() => openEdit(group)}>
                          {t("common.edit")}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDelete(group.id)}
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
          </CardContent>
        </Card>
      )}
    </div>
  );
}
