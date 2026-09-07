"use client";

import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { FormSkeleton } from "@/components/ui/skeletons";
import {
  useMembershipTypes,
  useUpdateMembershipType,
} from "@/features/members/hooks/use-members";
import { useSettings, useUpdateSettings } from "../hooks/use-settings";

/**
 * Public sign-up as the single decision it is: whether strangers may join at
 * all, whether an admin reviews them, and which free tier they land on. The two
 * switches and the tier are separate stores — `organization_settings.features`
 * and `membership_types.is_default` — but an admin reads them as one rule, so
 * the panel states the resulting behaviour in words above the controls.
 */
export function RegistrationSettings() {
  const t = useTranslations();
  const { data: settings, isLoading } = useSettings();
  const { data: types, isLoading: typesLoading } = useMembershipTypes();
  const updateSettings = useUpdateSettings();
  const updateType = useUpdateMembershipType();

  const features = settings?.features ?? {};
  // Both keys are absent on a fresh install and both default to on there —
  // `get_registration_settings` reads them the same way.
  const publicRegistration = features.public_registration !== false;
  const requiresApproval = features.registration_requires_approval !== false;

  const defaultType = types?.find((type) => type.is_default) ?? null;
  // Only a free tier may be the default, and the database enforces it. An
  // inactive default still belongs in the list: it is what sign-ups land on
  // until the admin moves the flag.
  const freeTypes =
    types?.filter((type) => type.base_price === 0 && (type.is_active || type.is_default)) ?? [];

  const flow = !publicRegistration
    ? "flowClosed"
    : requiresApproval
      ? "flowApproval"
      : "flowImmediate";

  if (isLoading || typesLoading) return <FormSkeleton fields={3} />;

  async function saveFeature(partial: Record<string, unknown>) {
    try {
      await updateSettings.mutateAsync({
        features: { ...(settings?.features ?? {}), ...partial },
      });
      toast.success(t("toast.success.saved"));
    } catch {
      /* global handler shows the error toast */
    }
  }

  async function chooseDefault(value: string) {
    try {
      await updateType.mutateAsync({
        id: Number(value),
        data: { is_default: true },
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
          <CardTitle className="text-base">
            {t("settings.registration.title")}
          </CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-3 pt-0 space-y-3">
          <p className="rounded-lg border bg-muted/50 p-2.5 text-xs text-muted-foreground">
            {t(`settings.registration.${flow}`)}
          </p>

          <div className="flex items-center justify-between gap-2 rounded-lg border p-2.5">
            <div>
              <p className="text-xs font-medium">
                {t("settings.registration.publicEnabled")}
              </p>
              <p className="text-xs text-muted-foreground">
                {t("settings.registration.publicEnabledDesc")}
              </p>
            </div>
            <Switch
              checked={publicRegistration}
              onCheckedChange={(checked) =>
                saveFeature({ public_registration: checked })
              }
              disabled={updateSettings.isPending}
            />
          </div>

          {publicRegistration && (
            <div className="flex items-center justify-between gap-2 rounded-lg border p-2.5">
              <div>
                <p className="text-xs font-medium">
                  {t("settings.registration.requiresApproval")}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t("settings.registration.requiresApprovalDesc")}
                </p>
              </div>
              <Switch
                checked={requiresApproval}
                onCheckedChange={(checked) =>
                  saveFeature({ registration_requires_approval: checked })
                }
                disabled={updateSettings.isPending}
              />
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-base">
            {t("settings.registration.defaultTier")}
          </CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-3 pt-0 space-y-1">
          <Label className="text-xs">
            {t("settings.registration.defaultTierLabel")}
          </Label>
          <Select
            value={defaultType ? String(defaultType.id) : ""}
            onValueChange={chooseDefault}
            disabled={updateType.isPending || freeTypes.length === 0}
          >
            <SelectTrigger className="h-8 w-full sm:w-72">
              <SelectValue
                placeholder={t("settings.registration.noDefaultTier")}
              />
            </SelectTrigger>
            <SelectContent>
              {freeTypes.map((type) => (
                <SelectItem key={type.id} value={String(type.id)}>
                  {type.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            {freeTypes.length === 0
              ? t("settings.registration.noFreeTiers")
              : t("settings.registration.defaultTierDesc")}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
