"use client";

import { useTranslations } from "next-intl";
import { AlertTriangle } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { usePermissions } from "@/features/auth/hooks/use-permissions";
import { usePaymentOptions } from "../hooks/use-activities";
import {
  PAYMENT_METHODS,
  type ActivityData,
  type PaymentFlow,
  type PaymentMethod,
} from "../services/activities-api";

export type AutoCancel = "inherit" | "on" | "off";

export interface PaymentSettings {
  payment_methods: PaymentMethod[];
  auto_cancel: AutoCancel;
  auto_cancel_hours: string;
}

/** An activity's payment settings, or a space's: they carry the same fields (#603). */
export function paymentSettingsFrom(
  owner?: Pick<ActivityData, "payment_methods" | "auto_cancel_enabled" | "auto_cancel_hours">
): PaymentSettings {
  const override = owner?.auto_cancel_enabled;
  return {
    payment_methods: owner?.payment_methods ?? [],
    auto_cancel: override == null ? "inherit" : override ? "on" : "off",
    auto_cancel_hours: owner?.auto_cancel_hours?.toString() ?? "",
  };
}

export function paymentSettingsPayload(settings: PaymentSettings) {
  const hours = settings.auto_cancel === "on" && settings.auto_cancel_hours
    ? Number(settings.auto_cancel_hours)
    : null;
  return {
    payment_methods: settings.payment_methods,
    auto_cancel_enabled: settings.auto_cancel === "inherit" ? null : settings.auto_cancel === "on",
    auto_cancel_hours: hours,
  };
}

interface ActivityPaymentFieldsProps {
  flow: PaymentFlow;
  value: PaymentSettings;
  onChange: (value: PaymentSettings) => void;
}

/** How a pay-to-confirm activity is paid, and whether unpaid seats expire. */
export function ActivityPaymentFields({ flow, value, onChange }: ActivityPaymentFieldsProps) {
  const t = useTranslations();
  const { has, hasRole } = usePermissions();
  const { data: options } = usePaymentOptions(flow !== "legacy");
  // Each fix points at the screen only for someone who can open it; anyone
  // else is told who can do it rather than sent to a tab they lack.
  const fixIt = (count: number) =>
    has("settings.communications.write")
      ? t("activities.payment.fixInSettings", { count })
      : t("activities.payment.fixAskAdmin");
  // Settings › Payments is the super admin's: providers and IBAN are credentials.
  const paymentsReachable = hasRole("super_admin");

  if (flow === "legacy") {
    return (
      <div className="space-y-1">
        <Label>{t("activities.payment.title")}</Label>
        <p className="text-sm text-muted-foreground">{t("activities.payment.legacyNotice")}</p>
      </div>
    );
  }

  const usable = new Set(options?.usable_methods ?? []);
  const switchedOff = options?.switched_off_templates ?? [];
  const templateNames = switchedOff
    .map((key) => t(`settings.emailTemplates.templates.${key}.name`))
    .join(", ");
  const clubSetting = options?.auto_cancel_enabled
    ? t("activities.payment.clubOn", { hours: options.auto_cancel_hours })
    : t("activities.payment.clubOff");

  function toggleMethod(method: PaymentMethod, checked: boolean) {
    onChange({
      ...value,
      payment_methods: checked
        ? [...value.payment_methods, method]
        : value.payment_methods.filter((m) => m !== method),
    });
  }

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        <Label>{t("activities.payment.methods")}</Label>
        <p className="text-sm text-muted-foreground">{t("activities.payment.methodsHint")}</p>
        <div className="grid gap-2 sm:grid-cols-2">
          {PAYMENT_METHODS.map((method) => {
            const available = usable.has(method);
            const checked = value.payment_methods.includes(method);
            return (
              <label key={method} className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={checked}
                  disabled={!available && !checked}
                  onCheckedChange={(c) => toggleMethod(method, c === true)}
                />
                <span className={available ? undefined : "text-muted-foreground"}>
                  {t(`activities.payment.method.${method}`)}
                </span>
                {!available && options && (
                  <span className="text-xs text-muted-foreground">
                    ({t(`activities.payment.unavailable.${method}`)}
                    {method !== "cash" &&
                      ` ${t(
                        paymentsReachable
                          ? "activities.payment.unavailableWhere"
                          : "activities.payment.unavailableAsk"
                      )}`})
                  </span>
                )}
              </label>
            );
          })}
        </div>
        {switchedOff.includes("registration_pending_payment") && (
          <PaymentWarning>
            {t("activities.payment.pendingEmailOff")} {fixIt(1)}
          </PaymentWarning>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-2">
          <Label>{t("activities.payment.autoCancel")}</Label>
          <Select
            value={value.auto_cancel}
            onValueChange={(v) => onChange({ ...value, auto_cancel: v as AutoCancel })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="inherit">
                {t("activities.payment.autoCancelInherit", { setting: clubSetting })}
              </SelectItem>
              <SelectItem value="on">{t("activities.payment.autoCancelOn")}</SelectItem>
              <SelectItem value="off">{t("activities.payment.autoCancelOff")}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        {value.auto_cancel === "on" && (
          <div className="space-y-2">
            <Label htmlFor="auto-cancel-hours">{t("activities.payment.autoCancelHours")}</Label>
            <Input
              id="auto-cancel-hours"
              type="number"
              min={1}
              max={8760}
              placeholder={options ? String(options.auto_cancel_hours) : undefined}
              value={value.auto_cancel_hours}
              onChange={(e) => onChange({ ...value, auto_cancel_hours: e.target.value })}
            />
          </div>
        )}
      </div>
      {value.auto_cancel === "on" && switchedOff.length > 0 && (
        <PaymentWarning>
          {t("activities.payment.autoCancelNeedsEmails", { templates: templateNames })}{" "}
          {fixIt(switchedOff.length)}
        </PaymentWarning>
      )}
      {value.auto_cancel === "on" && (
        <p className="text-sm text-muted-foreground">{t("activities.payment.autoCancelStartsNow")}</p>
      )}
    </div>
  );
}

export function PaymentWarning({ children }: { children: React.ReactNode }) {
  return (
    <p className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 p-2 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <span>{children}</span>
    </p>
  );
}
