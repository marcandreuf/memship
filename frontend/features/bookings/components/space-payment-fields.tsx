"use client";

import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
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
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { usePermissions } from "@/features/auth/hooks/use-permissions";
import {
  PaymentWarning,
  type AutoCancel,
  type PaymentSettings,
} from "@/features/activities/components/activity-payment-fields";
import {
  PAYMENT_METHODS,
  type PaymentMethod,
} from "@/features/activities/services/activities-api";
import { useSpacePaymentOptions } from "../hooks/use-bookings";
import type { SpacePaymentFlow } from "../services/bookings-api";

interface SpacePaymentFieldsProps {
  flow: SpacePaymentFlow;
  /** The flow the space has now; a switch only goes from legacy to pay-to-confirm. */
  savedFlow: SpacePaymentFlow;
  onSwitchFlow: () => void;
  value: PaymentSettings;
  onChange: (value: PaymentSettings) => void;
}

/**
 * How a pay-to-confirm space is paid, and whether an unpaid booking may be
 * released before the cut-off (#603). A legacy space shows its flow and the
 * one-way switch instead.
 */
export function SpacePaymentFields({
  flow,
  savedFlow,
  onSwitchFlow,
  value,
  onChange,
}: SpacePaymentFieldsProps) {
  const t = useTranslations();
  const { has, hasRole } = usePermissions();
  const { data: options } = useSpacePaymentOptions();
  const [confirmDialog, confirm] = useConfirmDialog();
  const fixIt = (count: number) =>
    has("settings.communications.write")
      ? t("activities.payment.fixInSettings", { count })
      : t("activities.payment.fixAskAdmin");
  const paymentsReachable = hasRole("super_admin");
  const switchedOff = options?.switched_off_templates ?? [];

  if (flow === "legacy") {
    return (
      <div className="space-y-2">
        {confirmDialog}
        <Label>{t("activities.payment.title")}</Label>
        <p className="text-sm text-muted-foreground">{t("bookings.payment.legacyNotice")}</p>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() =>
            confirm({
              title: t("bookings.payment.switchTitle"),
              description: t("bookings.payment.switchDescription"),
              cancelLabel: t("common.back"),
              confirmLabel: t("bookings.payment.switchConfirm"),
              onConfirm: onSwitchFlow,
            })
          }
        >
          {t("bookings.payment.switch")}
        </Button>
      </div>
    );
  }

  const usable = new Set(options?.usable_methods ?? []);
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
      {savedFlow === "legacy" && (
        <PaymentWarning>{t("bookings.payment.switchPending")}</PaymentWarning>
      )}
      <div className="space-y-2">
        <Label>{t("activities.payment.methods")}</Label>
        <p className="text-sm text-muted-foreground">{t("bookings.payment.methodsHint")}</p>
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
        {switchedOff.length > 0 && (
          <PaymentWarning>
            {t("bookings.payment.emailsOff", { templates: templateNames })}{" "}
            {fixIt(switchedOff.length)}
          </PaymentWarning>
        )}
      </div>

      <p className="text-sm text-muted-foreground">{t("bookings.payment.deadlineHint")}</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-2">
          <Label>{t("bookings.payment.autoCancel")}</Label>
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
              <SelectItem value="on">{t("bookings.payment.autoCancelOn")}</SelectItem>
              <SelectItem value="off">{t("bookings.payment.autoCancelOff")}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        {value.auto_cancel === "on" && (
          <div className="space-y-2">
            <Label htmlFor="space-auto-cancel-hours">
              {t("activities.payment.autoCancelHours")}
            </Label>
            <Input
              id="space-auto-cancel-hours"
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
      {value.auto_cancel === "on" && (
        <p className="text-sm text-muted-foreground">{t("bookings.payment.autoCancelStartsNow")}</p>
      )}
    </div>
  );
}
