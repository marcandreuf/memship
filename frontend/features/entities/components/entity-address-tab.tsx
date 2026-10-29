"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { useZodResolver } from "@/hooks/use-zod-resolver";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Form, FormControl, FormField, FormItem, FormLabel, FormMessage,
} from "@/components/ui/form";
import { TabContentSkeleton } from "@/components/ui/skeletons";
import { toast } from "sonner";
import { mapApiErrorsToForm } from "@/lib/errors";
import { useEntityAddress, useUpdateEntityAddress } from "../hooks/use-entities";
import type { EntityAddress } from "../services/entities-api";
import { usePermissions } from "@/features/auth/hooks/use-permissions";

const addressSchema = z.object({
  address_line1: z.string().trim().min(1).max(255),
  address_line2: z.string().max(255).optional().or(z.literal("")),
  city: z.string().trim().min(1).max(100),
  state_province: z.string().max(100).optional().or(z.literal("")),
  postal_code: z.string().max(20).optional().or(z.literal("")),
  country: z.string().max(3).optional().or(z.literal("")),
});
type AddressFormValues = z.infer<typeof addressSchema>;

interface EntityAddressTabProps {
  entityId: number;
}

export function EntityAddressTab({ entityId }: EntityAddressTabProps) {
  const t = useTranslations();
  const { has } = usePermissions();
  const canWrite = has("entities.write");
  const { data: address, isLoading } = useEntityAddress(entityId);
  const [isEditing, setIsEditing] = useState(false);

  if (isLoading) return <TabContentSkeleton />;

  if (isEditing) {
    return (
      <AddressForm
        entityId={entityId}
        address={address ?? null}
        onDone={() => setIsEditing(false)}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        {canWrite && (
          <Button variant="outline" size="sm" onClick={() => setIsEditing(true)}>
            {address ? t("common.edit") : t("entities.addAddress")}
          </Button>
        )}
      </div>
      {!address ? (
        <p className="text-sm text-muted-foreground">{t("entities.noAddress")}</p>
      ) : (
        <div className="text-sm space-y-1">
          <p>{address.address_line1}</p>
          {address.address_line2 && <p>{address.address_line2}</p>}
          <p>
            {[address.postal_code, address.city].filter(Boolean).join(" ")}
          </p>
          {(address.state_province || address.country) && (
            <p className="text-muted-foreground">
              {[address.state_province, address.country].filter(Boolean).join(", ")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function AddressForm({
  entityId,
  address,
  onDone,
}: {
  entityId: number;
  address: EntityAddress | null;
  onDone: () => void;
}) {
  const t = useTranslations();
  const mutation = useUpdateEntityAddress(entityId);

  const form = useForm<AddressFormValues>({
    resolver: useZodResolver(addressSchema),
    defaultValues: {
      address_line1: address?.address_line1 || "",
      address_line2: address?.address_line2 || "",
      city: address?.city || "",
      state_province: address?.state_province || "",
      postal_code: address?.postal_code || "",
      country: address?.country || "ES",
    },
  });

  async function onSubmit(data: AddressFormValues) {
    const payload: Record<string, unknown> = {
      address_line1: data.address_line1,
      city: data.city,
      address_line2: data.address_line2 || null,
      state_province: data.state_province || null,
      postal_code: data.postal_code || null,
      country: data.country || "ES",
    };
    try {
      await mutation.mutateAsync(payload);
      toast.success(t("toast.success.saved"));
      onDone();
    } catch (error) {
      mapApiErrorsToForm(error, form);
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-3">
          <FormField control={form.control} name="address_line1" render={({ field }) => (
            <FormItem className="sm:col-span-2">
              <FormLabel>{t("settings.addressLine1")}</FormLabel>
              <FormControl><Input {...field} /></FormControl>
              <FormMessage />
            </FormItem>
          )} />
          <FormField control={form.control} name="address_line2" render={({ field }) => (
            <FormItem>
              <FormLabel>{t("settings.addressLine2")}</FormLabel>
              <FormControl><Input {...field} /></FormControl>
              <FormMessage />
            </FormItem>
          )} />
          <FormField control={form.control} name="city" render={({ field }) => (
            <FormItem>
              <FormLabel>{t("settings.city")}</FormLabel>
              <FormControl><Input {...field} /></FormControl>
              <FormMessage />
            </FormItem>
          )} />
          <FormField control={form.control} name="postal_code" render={({ field }) => (
            <FormItem>
              <FormLabel>{t("settings.postalCode")}</FormLabel>
              <FormControl><Input {...field} /></FormControl>
              <FormMessage />
            </FormItem>
          )} />
          <FormField control={form.control} name="state_province" render={({ field }) => (
            <FormItem>
              <FormLabel>{t("settings.stateProvince")}</FormLabel>
              <FormControl><Input {...field} /></FormControl>
              <FormMessage />
            </FormItem>
          )} />
          <FormField control={form.control} name="country" render={({ field }) => (
            <FormItem>
              <FormLabel>{t("settings.country")}</FormLabel>
              <FormControl><Input {...field} maxLength={3} /></FormControl>
              <FormMessage />
            </FormItem>
          )} />
        </div>
        <div className="flex gap-2">
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? t("common.loading") : t("common.save")}
          </Button>
          <Button type="button" variant="outline" onClick={onDone}>
            {t("common.cancel")}
          </Button>
        </div>
      </form>
    </Form>
  );
}
