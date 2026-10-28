"use client";

import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { useZodResolver } from "@/hooks/use-zod-resolver";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Form, FormControl, FormField, FormItem, FormLabel, FormMessage,
} from "@/components/ui/form";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { mapApiErrorsToForm } from "@/lib/errors";
import { useEntityKinds } from "../hooks/use-entities";
import type { EntityData } from "../services/entities-api";

const entitySchema = z.object({
  kind: z.string().min(1),
  name: z.string().trim().min(1).max(255),
  national_id: z.string().max(50).optional().or(z.literal("")),
  email: z.string().email().max(255).optional().or(z.literal("")),
});
type EntityFormValues = z.infer<typeof entitySchema>;

interface EntityFormProps {
  entity?: EntityData;
  onSubmit: (data: EntityFormValues) => Promise<void>;
  isSubmitting: boolean;
  onCancel?: () => void;
}

export function EntityForm({ entity, onSubmit, isSubmitting, onCancel }: EntityFormProps) {
  const t = useTranslations();
  const { data: kinds = [] } = useEntityKinds();

  const form = useForm<EntityFormValues>({
    resolver: useZodResolver(entitySchema),
    defaultValues: {
      kind: entity?.kind || "company",
      name: entity?.name || "",
      national_id: entity?.national_id || "",
      email: entity?.email || "",
    },
  });

  async function handleSubmit(data: EntityFormValues) {
    try {
      await onSubmit(data);
    } catch (error) {
      mapApiErrorsToForm(error, form);
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField control={form.control} name="name" render={({ field }) => (
            <FormItem>
              <FormLabel>{t("entities.name")}</FormLabel>
              <FormControl><Input {...field} /></FormControl>
              <FormMessage />
            </FormItem>
          )} />
          <FormField control={form.control} name="kind" render={({ field }) => (
            <FormItem>
              <FormLabel>{t("entities.kind")}</FormLabel>
              <Select onValueChange={field.onChange} value={field.value}>
                <FormControl><SelectTrigger><SelectValue /></SelectTrigger></FormControl>
                <SelectContent>
                  {kinds.map((k) => (
                    <SelectItem key={k.code} value={k.code}>
                      {t(`entities.kinds.${k.code}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )} />
          <FormField control={form.control} name="national_id" render={({ field }) => (
            <FormItem>
              <FormLabel>{t("entities.nationalId")}</FormLabel>
              <FormControl><Input {...field} placeholder="B12345678" /></FormControl>
              <FormMessage />
            </FormItem>
          )} />
          <FormField control={form.control} name="email" render={({ field }) => (
            <FormItem>
              <FormLabel>{t("auth.email")}</FormLabel>
              <FormControl><Input {...field} type="email" /></FormControl>
              <FormMessage />
            </FormItem>
          )} />
        </div>
        <div className="flex gap-2">
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? t("common.loading") : t("common.save")}
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
