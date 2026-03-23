"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { toast } from "sonner";
import { mapApiErrorsToForm } from "@/lib/errors";
import { useUpdateGroup } from "../hooks/use-groups";
import type { GroupData } from "../services/groups-api";

const groupSchema = z.object({
  name: z.string().min(1).max(255),
  description: z.string().max(2000).optional(),
  is_billable: z.boolean().optional(),
  color: z.string().regex(/^#[0-9a-fA-F]{6}$/).optional().or(z.literal("")),
});

type GroupFormValues = z.infer<typeof groupSchema>;

interface GroupEditFormProps {
  group: GroupData;
  onSuccess: () => void;
  onCancel: () => void;
}

export function GroupEditForm({ group, onSuccess, onCancel }: GroupEditFormProps) {
  const t = useTranslations();
  const updateMutation = useUpdateGroup();

  const form = useForm<GroupFormValues>({
    resolver: zodResolver(groupSchema),
    defaultValues: {
      name: group.name,
      description: group.description || "",
      is_billable: group.is_billable,
      color: group.color || "",
    },
  });

  async function onSubmit(data: GroupFormValues) {
    const payload = {
      ...data,
      color: data.color || undefined,
    };
    try {
      await updateMutation.mutateAsync({ id: group.id, data: payload });
      toast.success(t("toast.success.saved"));
      onSuccess();
    } catch (error) {
      mapApiErrorsToForm(error, form);
    }
  }

  return (
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
        <div className="flex gap-3">
          <Button type="submit" disabled={updateMutation.isPending}>
            {updateMutation.isPending ? t("common.loading") : t("common.save")}
          </Button>
          <Button type="button" variant="outline" onClick={onCancel}>
            {t("common.cancel")}
          </Button>
        </div>
      </form>
    </Form>
  );
}
