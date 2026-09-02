"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useFieldArray, useForm } from "react-hook-form";
import { useZodResolver } from "@/hooks/use-zod-resolver";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { FormSkeleton, TabContentSkeleton } from "@/components/ui/skeletons";
import { toast } from "sonner";
import { mapApiErrorsToForm } from "@/lib/errors";
import { useSettings, useUpdateSettings } from "../hooks/use-settings";
import {
  useCreateCustomField,
  useCustomFields,
  useDeleteCustomField,
  useUpdateCustomField,
} from "@/features/custom-fields/hooks/use-custom-fields";
import type {
  CustomFieldDefinition,
  CustomFieldType,
} from "@/features/custom-fields/services/custom-fields-api";

const FIELD_TYPES: CustomFieldType[] = [
  "text",
  "textarea",
  "number",
  "date",
  "boolean",
  "select",
];

const definitionSchema = z
  .object({
    key: z
      .string()
      .min(1)
      .max(50)
      .regex(/^[a-z][a-z0-9_]*$/, "validation.invalidKey"),
    field_type: z.enum(["text", "textarea", "number", "date", "boolean", "select"]),
    label: z.string().min(1).max(100),
    label_es: z.string().max(100),
    label_ca: z.string().max(100),
    label_en: z.string().max(100),
    help_text: z.string().max(255),
    options: z.array(
      z.object({
        value: z.string().min(1).max(100),
        label: z.string().min(1).max(100),
      })
    ),
    required: z.boolean(),
    member_access: z.enum(["hidden", "read", "write"]),
    admin_access: z.enum(["read", "write"]),
    sort_order: z.coerce.number().int().min(0),
    active: z.boolean(),
  })
  .superRefine((data, ctx) => {
    if (data.field_type !== "select") return;
    if (data.options.length === 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["options"],
        message: "validation.selectNeedsOption",
      });
      return;
    }
    const values = data.options.map((o) => o.value);
    if (new Set(values).size !== values.length) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["options"],
        message: "validation.optionValuesUnique",
      });
    }
  });

type DefinitionFormValues = z.infer<typeof definitionSchema>;

export function ProfileFieldsSettings() {
  const t = useTranslations();
  const { data: settings, isLoading } = useSettings();
  const updateSettings = useUpdateSettings();

  const enabled = Boolean(settings?.features?.custom_profile_fields);
  // The definitions API 404s while the feature is off — don't ask until it's on.
  const { data: definitions = [], isLoading: loadingDefinitions } =
    useCustomFields(true, enabled);

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<CustomFieldDefinition | null>(null);

  if (isLoading) return <FormSkeleton fields={2} />;

  async function onToggle(checked: boolean) {
    try {
      // PUT /settings replaces the whole features dict — merge to keep siblings.
      await updateSettings.mutateAsync({
        features: {
          ...(settings?.features ?? {}),
          custom_profile_fields: checked,
        },
      });
      toast.success(t("toast.success.saved"));
    } catch {
      /* global handler shows the error toast */
    }
  }

  return (
    <div className="space-y-3 max-w-4xl">
      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-base">{t("profileFields.title")}</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-3 pt-0">
          <div className="flex items-center justify-between gap-2 rounded-lg border p-2.5">
            <div>
              <p className="text-xs font-medium">{t("profileFields.enabled")}</p>
              <p className="text-xs text-muted-foreground">
                {t("profileFields.enabledDesc")}
              </p>
            </div>
            <Switch
              checked={enabled}
              onCheckedChange={onToggle}
              disabled={updateSettings.isPending}
            />
          </div>
        </CardContent>
      </Card>

      {enabled && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between py-3 px-4">
            <CardTitle className="text-base">{t("profileFields.fields")}</CardTitle>
            <Dialog
              open={open}
              onOpenChange={(o) => {
                setOpen(o);
                if (!o) setEditing(null);
              }}
            >
              <DialogTrigger asChild>
                <Button variant="outline" size="sm" onClick={() => setEditing(null)}>
                  {t("profileFields.create")}
                </Button>
              </DialogTrigger>
              <DialogContent className="max-h-[85vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>
                    {editing ? t("profileFields.edit") : t("profileFields.create")}
                  </DialogTitle>
                </DialogHeader>
                <DefinitionForm
                  definition={editing}
                  onSuccess={() => {
                    setOpen(false);
                    setEditing(null);
                  }}
                />
              </DialogContent>
            </Dialog>
          </CardHeader>
          <CardContent className="px-4 pb-3 pt-0 table-compact">
            {loadingDefinitions ? (
              <TabContentSkeleton />
            ) : !definitions.length ? (
              <p className="text-sm text-muted-foreground">
                {t("profileFields.noFields")}
              </p>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("profileFields.label")}</TableHead>
                      <TableHead>{t("profileFields.key")}</TableHead>
                      <TableHead>{t("profileFields.type")}</TableHead>
                      <TableHead>{t("profileFields.memberAccess")}</TableHead>
                      <TableHead>{t("profileFields.adminAccess")}</TableHead>
                      <TableHead>{t("profileFields.order")}</TableHead>
                      <TableHead>{t("common.actions")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {definitions.map((definition) => (
                      <DefinitionRow
                        key={definition.id}
                        definition={definition}
                        onEdit={() => {
                          setEditing(definition);
                          setOpen(true);
                        }}
                      />
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function DefinitionRow({
  definition,
  onEdit,
}: {
  definition: CustomFieldDefinition;
  onEdit: () => void;
}) {
  const t = useTranslations();
  const deleteMutation = useDeleteCustomField();
  const [confirmDialog, confirmAction] = useConfirmDialog();

  return (
    <TableRow className={definition.active ? undefined : "opacity-60"}>
      <TableCell className="font-medium">
        {definition.label}
        {definition.required && <span className="text-destructive"> *</span>}
        {!definition.active && (
          <Badge variant="secondary" className="ml-2">
            {t("profileFields.retired")}
          </Badge>
        )}
      </TableCell>
      <TableCell className="font-mono text-xs">{definition.key}</TableCell>
      <TableCell>{t(`profileFields.types.${definition.field_type}`)}</TableCell>
      <TableCell>
        <Badge
          variant={definition.member_access === "write" ? "default" : "secondary"}
        >
          {t(`profileFields.access.${definition.member_access}`)}
        </Badge>
      </TableCell>
      <TableCell>
        <Badge variant={definition.admin_access === "write" ? "default" : "secondary"}>
          {t(`profileFields.access.${definition.admin_access}`)}
        </Badge>
      </TableCell>
      <TableCell>{definition.sort_order}</TableCell>
      <TableCell>
        <div className="flex gap-2">
          {confirmDialog}
          <Button variant="outline" size="sm" onClick={onEdit}>
            {t("common.edit")}
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={deleteMutation.isPending}
            onClick={() => {
              confirmAction({
                // A field that already holds values is retired, not erased.
                title: t("profileFields.confirmDelete"),
                cancelLabel: t("common.cancel"),
                confirmLabel: t("common.delete"),
                onConfirm: async () => {
                  try {
                    await deleteMutation.mutateAsync(definition.id);
                    toast.success(t("toast.success.deleted"));
                  } catch {
                    /* global handler shows the error toast */
                  }
                },
              });
            }}
          >
            {t("common.delete")}
          </Button>
        </div>
      </TableCell>
    </TableRow>
  );
}

function DefinitionForm({
  definition,
  onSuccess,
}: {
  definition: CustomFieldDefinition | null;
  onSuccess: () => void;
}) {
  const t = useTranslations();
  const createMutation = useCreateCustomField();
  const updateMutation = useUpdateCustomField();

  const form = useForm<DefinitionFormValues>({
    resolver: useZodResolver(definitionSchema),
    defaultValues: {
      key: definition?.key ?? "",
      field_type: definition?.field_type ?? "text",
      label: definition?.label ?? "",
      label_es: definition?.labels?.es ?? "",
      label_ca: definition?.labels?.ca ?? "",
      label_en: definition?.labels?.en ?? "",
      help_text: definition?.help_text ?? "",
      options: definition?.options ?? [],
      required: definition?.required ?? false,
      member_access: definition?.member_access ?? "read",
      admin_access: definition?.admin_access ?? "write",
      sort_order: definition?.sort_order ?? 0,
      active: definition?.active ?? true,
    },
  });

  const optionFields = useFieldArray({ control: form.control, name: "options" });
  const fieldType = form.watch("field_type");

  async function onSubmit(data: DefinitionFormValues) {
    const labels: Record<string, string> = {};
    if (data.label_es) labels.es = data.label_es;
    if (data.label_ca) labels.ca = data.label_ca;
    if (data.label_en) labels.en = data.label_en;

    const common = {
      label: data.label,
      labels,
      help_text: data.help_text || null,
      options: data.field_type === "select" ? data.options : null,
      required: data.required,
      member_access: data.member_access,
      admin_access: data.admin_access,
      sort_order: data.sort_order,
      active: data.active,
    };

    try {
      if (definition) {
        // key and field_type are immutable — the API ignores them anyway.
        await updateMutation.mutateAsync({ id: definition.id, data: common });
      } else {
        await createMutation.mutateAsync({
          ...common,
          key: data.key,
          field_type: data.field_type,
        });
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
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="key"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("profileFields.key")}</FormLabel>
                <FormControl>
                  <Input
                    placeholder="shirt_size"
                    disabled={Boolean(definition)}
                    {...field}
                  />
                </FormControl>
                <FormDescription className="text-xs">
                  {t("profileFields.keyHint")}
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="field_type"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("profileFields.type")}</FormLabel>
                <Select
                  value={field.value}
                  onValueChange={field.onChange}
                  disabled={Boolean(definition)}
                >
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {FIELD_TYPES.map((type) => (
                      <SelectItem key={type} value={type}>
                        {t(`profileFields.types.${type}`)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormDescription className="text-xs">
                  {t("profileFields.typeHint")}
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <FormField
          control={form.control}
          name="label"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t("profileFields.label")}</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="grid gap-3 sm:grid-cols-3">
          {(["es", "ca", "en"] as const).map((locale) => (
            <FormField
              key={locale}
              control={form.control}
              name={`label_${locale}` as const}
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-xs">
                    {t(`profileFields.labelLocale.${locale}`)}
                  </FormLabel>
                  <FormControl>
                    <Input className="h-8" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          ))}
        </div>

        <FormField
          control={form.control}
          name="help_text"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t("profileFields.helpText")}</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {fieldType === "select" && (
          <div className="space-y-2 rounded-lg border p-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">{t("profileFields.options")}</p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => optionFields.append({ value: "", label: "" })}
              >
                {t("profileFields.addOption")}
              </Button>
            </div>
            {optionFields.fields.map((option, index) => (
              <div key={option.id} className="flex items-start gap-2">
                <FormField
                  control={form.control}
                  name={`options.${index}.value`}
                  render={({ field }) => (
                    <FormItem className="flex-1">
                      <FormControl>
                        <Input
                          className="h-8"
                          placeholder={t("profileFields.optionValue")}
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name={`options.${index}.label`}
                  render={({ field }) => (
                    <FormItem className="flex-1">
                      <FormControl>
                        <Input
                          className="h-8"
                          placeholder={t("profileFields.optionLabel")}
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => optionFields.remove(index)}
                >
                  {t("common.delete")}
                </Button>
              </div>
            ))}
            {form.formState.errors.options?.message && (
              <p className="text-sm text-destructive">
                {form.formState.errors.options.message}
              </p>
            )}
          </div>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="member_access"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("profileFields.memberAccess")}</FormLabel>
                <Select value={field.value} onValueChange={field.onChange}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {(["hidden", "read", "write"] as const).map((level) => (
                      <SelectItem key={level} value={level}>
                        {t(`profileFields.access.${level}`)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormDescription className="text-xs">
                  {t("profileFields.memberAccessHint")}
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="admin_access"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("profileFields.adminAccess")}</FormLabel>
                <Select value={field.value} onValueChange={field.onChange}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {(["read", "write"] as const).map((level) => (
                      <SelectItem key={level} value={level}>
                        {t(`profileFields.access.${level}`)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormDescription className="text-xs">
                  {t("profileFields.adminAccessHint")}
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="sort_order"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("profileFields.order")}</FormLabel>
                <FormControl>
                  <Input className="h-8" type="number" min={0} {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <div className="flex items-end gap-4 pb-1">
            <FormField
              control={form.control}
              name="required"
              render={({ field }) => (
                <FormItem className="flex items-center gap-2">
                  <FormControl>
                    <Checkbox
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  </FormControl>
                  <FormLabel className="!mt-0">
                    {t("profileFields.required")}
                  </FormLabel>
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="active"
              render={({ field }) => (
                <FormItem className="flex items-center gap-2">
                  <FormControl>
                    <Checkbox
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  </FormControl>
                  <FormLabel className="!mt-0">
                    {t("profileFields.active")}
                  </FormLabel>
                </FormItem>
              )}
            />
          </div>
        </div>

        <Button type="submit" disabled={isPending} className="w-full">
          {isPending ? t("common.loading") : t("common.save")}
        </Button>
      </form>
    </Form>
  );
}
