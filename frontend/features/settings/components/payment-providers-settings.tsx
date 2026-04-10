"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Plus, TestTube, Trash2, Settings2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FormSkeleton } from "@/components/ui/skeletons";
import {
  usePaymentProviders,
  useProviderTypes,
  useCreatePaymentProvider,
  useUpdatePaymentProvider,
  useDeletePaymentProvider,
  useTogglePaymentProvider,
  useTestPaymentProvider,
} from "../hooks/use-payment-providers";
import type {
  PaymentProvider,
  ProviderTypeSchema,
  ProviderField,
} from "../services/payment-providers-api";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "outline"> = {
  active: "default",
  test: "secondary",
  disabled: "outline",
};

const PROVIDER_ICONS: Record<string, string> = {
  sepa_direct_debit: "🏦",
  stripe: "💳",
  redsys: "🏧",
  goCardless: "🔄",
  paypal: "🅿️",
};

export function PaymentProvidersSettings() {
  const t = useTranslations();
  const { data, isLoading } = usePaymentProviders();
  const { data: providerTypes } = useProviderTypes();
  const createMutation = useCreatePaymentProvider();
  const updateMutation = useUpdatePaymentProvider();
  const deleteMutation = useDeletePaymentProvider();
  const toggleMutation = useTogglePaymentProvider();
  const testMutation = useTestPaymentProvider();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<PaymentProvider | null>(null);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [configValues, setConfigValues] = useState<Record<string, string>>({});
  const [displayName, setDisplayName] = useState("");
  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({});

  const providers = data?.items ?? [];
  const configuredTypes = new Set(providers.map((p) => p.provider_type));

  function openCreate() {
    setEditingProvider(null);
    setSelectedType(null);
    setConfigValues({});
    setDisplayName("");
    setShowPasswords({});
    setDialogOpen(true);
  }

  function openEdit(provider: PaymentProvider) {
    setEditingProvider(provider);
    setSelectedType(provider.provider_type);
    setConfigValues({ ...provider.config });
    setDisplayName(provider.display_name);
    setShowPasswords({});
    setDialogOpen(true);
  }

  function selectType(type: string) {
    setSelectedType(type);
    const schema = providerTypes?.find((t) => t.provider_type === type);
    if (schema) {
      const defaults: Record<string, string> = {};
      for (const field of schema.fields) {
        defaults[field.key] = "";
      }
      setConfigValues(defaults);
      setDisplayName(
        type
          .replace(/_/g, " ")
          .replace(/\b\w/g, (c) => c.toUpperCase())
      );
    }
  }

  async function handleSave() {
    if (!selectedType) return;
    try {
      if (editingProvider) {
        await updateMutation.mutateAsync({
          id: editingProvider.id,
          data: { display_name: displayName, config: configValues },
        });
        toast.success(t("toast.success.saved"));
      } else {
        await createMutation.mutateAsync({
          provider_type: selectedType,
          display_name: displayName,
          status: "disabled",
          config: configValues,
        });
        toast.success(t("toast.success.created"));
      }
      setDialogOpen(false);
    } catch {
      toast.error(t("toast.error.generic"));
    }
  }

  async function handleDelete(provider: PaymentProvider) {
    try {
      await deleteMutation.mutateAsync(provider.id);
      toast.success(t("toast.success.deleted"));
    } catch {
      toast.error(t("toast.error.generic"));
    }
  }

  async function handleToggle(provider: PaymentProvider) {
    try {
      await toggleMutation.mutateAsync(provider.id);
    } catch {
      toast.error(t("toast.error.generic"));
    }
  }

  async function handleTest(provider: PaymentProvider) {
    try {
      const result = await testMutation.mutateAsync(provider.id);
      if (result.success) {
        toast.success(t("settings.providers.testSuccess"));
      } else {
        toast.error(result.message);
      }
    } catch {
      toast.error(t("toast.error.generic"));
    }
  }

  function getSchema(): ProviderTypeSchema | undefined {
    if (!selectedType || !providerTypes) return undefined;
    return providerTypes.find((t) => t.provider_type === selectedType);
  }

  if (isLoading) return <FormSkeleton fields={3} />;

  return (
    <div className="space-y-3 max-w-4xl">
      <Card>
        <CardHeader className="py-3 px-4 flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-base">
              {t("settings.providers.title")}
            </CardTitle>
            <CardDescription className="text-xs">
              {t("settings.providers.description")}
            </CardDescription>
          </div>
          <Button size="sm" onClick={openCreate}>
            <Plus className="h-4 w-4 mr-1" />
            {t("settings.providers.add")}
          </Button>
        </CardHeader>
        <CardContent className="px-4 pb-3 pt-0">
          {providers.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              {t("settings.providers.empty")}
            </p>
          ) : (
            <div className="space-y-2">
              {providers.map((provider) => (
                <div
                  key={provider.id}
                  className="flex items-center justify-between rounded-lg border p-3"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-xl">
                      {PROVIDER_ICONS[provider.provider_type] ?? "💰"}
                    </span>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">
                          {provider.display_name}
                        </span>
                        <Badge variant={STATUS_VARIANT[provider.status] ?? "outline"}>
                          {t(`settings.providers.status.${provider.status}`)}
                        </Badge>
                        {provider.is_default && (
                          <Badge variant="secondary" className="text-xs">
                            {t("settings.providers.default")}
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {provider.provider_type}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={provider.status === "active"}
                      onCheckedChange={() => handleToggle(provider)}
                      disabled={toggleMutation.isPending}
                    />
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleTest(provider)}
                      disabled={testMutation.isPending}
                      title={t("settings.providers.test")}
                    >
                      <TestTube className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => openEdit(provider)}
                      title={t("settings.providers.edit")}
                    >
                      <Settings2 className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDelete(provider)}
                      disabled={deleteMutation.isPending}
                      title={t("settings.providers.delete")}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {editingProvider
                ? t("settings.providers.editTitle")
                : t("settings.providers.addTitle")}
            </DialogTitle>
          </DialogHeader>

          {/* Type selector (create only) */}
          {!editingProvider && !selectedType && (
            <div className="grid grid-cols-2 gap-2">
              {providerTypes?.map((typeSchema) => {
                const configured = configuredTypes.has(typeSchema.provider_type);
                return (
                  <button
                    key={typeSchema.provider_type}
                    className="flex items-center gap-2 rounded-lg border p-3 text-left hover:bg-accent disabled:opacity-50 disabled:cursor-not-allowed"
                    onClick={() => selectType(typeSchema.provider_type)}
                    disabled={configured}
                  >
                    <span className="text-xl">
                      {PROVIDER_ICONS[typeSchema.provider_type] ?? "💰"}
                    </span>
                    <div>
                      <p className="text-sm font-medium">
                        {t(`settings.providers.types.${typeSchema.provider_type}`)}
                      </p>
                      {configured && (
                        <p className="text-xs text-muted-foreground">
                          {t("settings.providers.configured")}
                        </p>
                      )}
                      {!typeSchema.available && !configured && (
                        <p className="text-xs text-muted-foreground">
                          {t("settings.providers.comingSoon")}
                        </p>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          {/* Config form */}
          {selectedType && (
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium">
                  {t("settings.providers.displayName")}
                </label>
                <Input
                  className="h-8 mt-1"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                />
              </div>

              {getSchema()?.fields.map((field: ProviderField) => (
                <div key={field.key}>
                  <label className="text-xs font-medium">
                    {field.label}
                    {field.required && (
                      <span className="text-destructive ml-0.5">*</span>
                    )}
                  </label>
                  {field.type === "select" ? (
                    <Select
                      value={configValues[field.key] || ""}
                      onValueChange={(v) =>
                        setConfigValues((prev) => ({ ...prev, [field.key]: v }))
                      }
                    >
                      <SelectTrigger className="h-8 mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {field.options?.map((opt) => (
                          <SelectItem key={opt} value={opt}>
                            {opt}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Input
                      className="h-8 mt-1 font-mono"
                      type={
                        field.type === "password" && !showPasswords[field.key]
                          ? "password"
                          : "text"
                      }
                      placeholder={field.placeholder}
                      value={configValues[field.key] || ""}
                      onChange={(e) =>
                        setConfigValues((prev) => ({
                          ...prev,
                          [field.key]: e.target.value,
                        }))
                      }
                    />
                  )}
                  {field.type === "password" && (
                    <button
                      type="button"
                      className="text-xs text-muted-foreground hover:text-foreground mt-0.5"
                      onClick={() =>
                        setShowPasswords((prev) => ({
                          ...prev,
                          [field.key]: !prev[field.key],
                        }))
                      }
                    >
                      {showPasswords[field.key]
                        ? t("settings.providers.hideValue")
                        : t("settings.providers.showValue")}
                    </button>
                  )}
                </div>
              ))}

              <div className="flex justify-end gap-2 pt-2">
                {!editingProvider && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setSelectedType(null)}
                  >
                    {t("common.back")}
                  </Button>
                )}
                <Button
                  size="sm"
                  onClick={handleSave}
                  disabled={
                    createMutation.isPending || updateMutation.isPending
                  }
                >
                  {createMutation.isPending || updateMutation.isPending
                    ? t("common.loading")
                    : t("common.save")}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
