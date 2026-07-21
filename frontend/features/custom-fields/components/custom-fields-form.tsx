"use client";

import { useEffect, useMemo } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Form,
  FormControl,
  FormDescription,
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
import { toast } from "sonner";
import { mapApiErrorsToForm } from "@/lib/errors";
import type {
  CustomFieldDefinition,
  CustomFieldValues,
} from "../services/custom-fields-api";

// Mirrors the backend caps in app/domains/custom_fields/service.py.
const TEXT_MAX = 255;
const TEXTAREA_MAX = 5000;

type FieldValue = string | boolean;
type FormValues = Record<string, FieldValue>;

/** The label for the active locale, falling back to the primary label. */
export function localizedLabel(
  definition: CustomFieldDefinition,
  locale: string
): string {
  return definition.labels?.[locale] || definition.label;
}

/** Stored values are canonical strings; the form wants typed values. */
function toFormValue(
  definition: CustomFieldDefinition,
  raw: string | null | undefined
): FieldValue {
  if (definition.field_type === "boolean") return raw === "true";
  return raw ?? "";
}

interface CustomFieldsFormProps {
  definitions: CustomFieldDefinition[];
  values: CustomFieldValues;
  onSave: (values: Record<string, FieldValue>) => Promise<unknown>;
  isSaving: boolean;
}

export function CustomFieldsForm({
  definitions,
  values,
  onSave,
  isSaving,
}: CustomFieldsFormProps) {
  const t = useTranslations();
  const locale = useLocale();

  const writable = useMemo(
    () => definitions.filter((d) => d.writable),
    [definitions]
  );
  const readOnly = useMemo(
    () => definitions.filter((d) => !d.writable),
    [definitions]
  );

  // Unlike every other form in the app, the shape isn't known at build time —
  // it's assembled from the definitions the API returned for this user.
  const schema = useMemo(() => {
    const shape: Record<string, z.ZodTypeAny> = {};
    for (const definition of writable) {
      let field: z.ZodTypeAny;
      switch (definition.field_type) {
        case "boolean":
          // A checkbox always carries a value, so `required` is already met.
          shape[definition.key] = z.boolean();
          continue;
        case "number":
          field = z
            .string()
            .refine(
              (v) => v === "" || !Number.isNaN(Number(v)),
              t("profileFields.validation.number")
            );
          break;
        case "textarea":
          field = z.string().max(TEXTAREA_MAX);
          break;
        default:
          field = z.string().max(TEXT_MAX);
      }
      if (definition.required) {
        field = field.refine(
          (v) => String(v).trim() !== "",
          t("profileFields.validation.required")
        );
      }
      shape[definition.key] = field;
    }
    return z.object(shape);
  }, [writable, t]);

  const defaultValues = useMemo(() => {
    const out: FormValues = {};
    for (const definition of writable) {
      out[definition.key] = toFormValue(definition, values[definition.key]);
    }
    return out;
  }, [writable, values]);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues,
  });

  // Values arrive after the first render, and can change under us after a save
  // elsewhere — keep the form in step without clobbering an in-progress edit.
  useEffect(() => {
    if (!form.formState.isDirty) form.reset(defaultValues);
  }, [defaultValues, form]);

  async function onSubmit(data: FormValues) {
    try {
      // Whole-map semantics: send every writable field, blank ones clear.
      await onSave(data);
      toast.success(t("toast.success.saved"));
      form.reset(data);
    } catch (error) {
      mapApiErrorsToForm(error, form);
    }
  }

  if (!definitions.length) {
    return (
      <p className="text-sm text-muted-foreground">
        {t("profileFields.noVisibleFields")}
      </p>
    );
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 max-w-2xl">
        <div className="grid gap-3 sm:grid-cols-2">
          {writable.map((definition) => (
            <FormField
              key={definition.id}
              control={form.control}
              name={definition.key}
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-xs">
                    {localizedLabel(definition, locale)}
                    {definition.required && (
                      <span className="text-destructive"> *</span>
                    )}
                  </FormLabel>
                  <FormControl>
                    <DynamicInput definition={definition} field={field} />
                  </FormControl>
                  {definition.help_text && (
                    <FormDescription className="text-xs">
                      {definition.help_text}
                    </FormDescription>
                  )}
                  <FormMessage />
                </FormItem>
              )}
            />
          ))}
        </div>

        {readOnly.length > 0 && (
          <div className="space-y-2 rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">
              {t("profileFields.readOnlyNotice")}
            </p>
            <dl className="grid gap-2 sm:grid-cols-2">
              {readOnly.map((definition) => (
                <div key={definition.id}>
                  <dt className="text-xs text-muted-foreground">
                    {localizedLabel(definition, locale)}
                  </dt>
                  <dd className="text-sm">
                    {displayValue(definition, values[definition.key], t)}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        )}

        {writable.length > 0 && (
          <Button type="submit" disabled={isSaving}>
            {isSaving ? t("common.loading") : t("profileFields.save")}
          </Button>
        )}
      </form>
    </Form>
  );
}

function displayValue(
  definition: CustomFieldDefinition,
  raw: string | null | undefined,
  t: ReturnType<typeof useTranslations>
): string {
  if (raw === null || raw === undefined || raw === "")
    return t("profileFields.empty");
  if (definition.field_type === "boolean")
    return raw === "true" ? t("profileFields.yes") : t("profileFields.no");
  if (definition.field_type === "select") {
    const option = definition.options?.find((o) => o.value === raw);
    return option?.label ?? raw;
  }
  return raw;
}

interface DynamicInputProps {
  definition: CustomFieldDefinition;
  field: {
    value: FieldValue;
    onChange: (value: FieldValue) => void;
    onBlur: () => void;
    name: string;
  };
}

/** One input per field type. No date picker exists in the project — the
 *  native date input is what every other form here uses. */
function DynamicInput({ definition, field }: DynamicInputProps) {
  switch (definition.field_type) {
    case "boolean":
      return (
        <div className="flex h-8 items-center">
          <Checkbox
            checked={Boolean(field.value)}
            onCheckedChange={(checked) => field.onChange(Boolean(checked))}
          />
        </div>
      );
    case "textarea":
      return (
        <Textarea
          rows={3}
          value={String(field.value)}
          onChange={(e) => field.onChange(e.target.value)}
          onBlur={field.onBlur}
          name={field.name}
        />
      );
    case "select":
      return (
        <Select
          value={String(field.value)}
          onValueChange={(value) => field.onChange(value)}
        >
          <SelectTrigger className="h-8">
            <SelectValue placeholder="—" />
          </SelectTrigger>
          <SelectContent>
            {(definition.options ?? []).map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      );
    case "number":
    case "date":
      return (
        <Input
          className="h-8"
          type={definition.field_type === "date" ? "date" : "number"}
          value={String(field.value)}
          onChange={(e) => field.onChange(e.target.value)}
          onBlur={field.onBlur}
          name={field.name}
        />
      );
    default:
      return (
        <Input
          className="h-8"
          value={String(field.value)}
          onChange={(e) => field.onChange(e.target.value)}
          onBlur={field.onBlur}
          name={field.name}
        />
      );
  }
}
