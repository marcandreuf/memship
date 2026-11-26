"use client";

import { useTranslations } from "next-intl";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export type LateCancellationMode = "block" | "allow_no_refund";
export type DeadlineUnit = "minutes" | "hours" | "days";

const UNIT_MINUTES: Record<DeadlineUnit, number> = {
  minutes: 1,
  hours: 60,
  days: 1440,
};

export interface CancellationPolicy {
  amount: string;
  unit: DeadlineUnit;
  mode: LateCancellationMode;
}

/** An activity's cancellation policy, or a space's: they carry the same fields (#604). */
export function cancellationPolicyFrom(
  owner?: {
    late_cancellation_mode?: string;
  } & (
    | { self_cancellation_deadline_minutes?: number | null }
    | { cancellation_deadline_minutes?: number | null }
  )
): CancellationPolicy {
  const minutes =
    owner && "self_cancellation_deadline_minutes" in owner
      ? owner.self_cancellation_deadline_minutes
      : owner && "cancellation_deadline_minutes" in owner
        ? owner.cancellation_deadline_minutes
        : null;
  const mode: LateCancellationMode =
    owner?.late_cancellation_mode === "allow_no_refund" ? "allow_no_refund" : "block";
  if (minutes == null) return { amount: "", unit: "hours", mode };
  // Shown in the largest unit that divides it evenly, so 1440 reads as 1 day.
  const unit: DeadlineUnit =
    minutes > 0 && minutes % 1440 === 0 ? "days" : minutes > 0 && minutes % 60 === 0 ? "hours" : "minutes";
  return { amount: String(minutes / UNIT_MINUTES[unit]), unit, mode };
}

/** The deadline in minutes; null when the field is empty. */
export function deadlineMinutes(policy: CancellationPolicy): number | null {
  if (policy.amount.trim() === "") return null;
  const n = Number(policy.amount);
  return Number.isFinite(n) && n >= 0 ? Math.round(n * UNIT_MINUTES[policy.unit]) : null;
}

interface CancellationPolicyFieldsProps {
  value: CancellationPolicy;
  onChange: (value: CancellationPolicy) => void;
  /** What an empty deadline means here: no deadline for an activity, the club default for a space. */
  emptyMeans: "none" | "clubDefault";
}

export function CancellationPolicyFields({
  value,
  onChange,
  emptyMeans,
}: CancellationPolicyFieldsProps) {
  const t = useTranslations();
  const hasDeadline = value.amount.trim() !== "";
  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <Label htmlFor="cancellation-deadline">
          {t("activities.cancellationRule.deadline")}
        </Label>
        <div className="flex gap-2">
          <Input
            id="cancellation-deadline"
            type="number"
            min={0}
            className="max-w-32"
            value={value.amount}
            onChange={(e) => onChange({ ...value, amount: e.target.value })}
          />
          <Select
            value={value.unit}
            onValueChange={(unit) => onChange({ ...value, unit: unit as DeadlineUnit })}
          >
            <SelectTrigger
              className="w-36"
              aria-label={t("activities.cancellationRule.unit")}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="minutes">{t("activities.cancellationRule.minutes")}</SelectItem>
              <SelectItem value="hours">{t("activities.cancellationRule.hours")}</SelectItem>
              <SelectItem value="days">{t("activities.cancellationRule.days")}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <p className="text-xs text-muted-foreground">
          {t(
            emptyMeans === "none"
              ? "activities.cancellationRule.hintNone"
              : "activities.cancellationRule.hintClubDefault"
          )}
        </p>
      </div>
      {(hasDeadline || emptyMeans === "clubDefault") && (
        <div className="space-y-1">
          <Label>{t("activities.cancellationRule.afterDeadline")}</Label>
          <Select
            value={value.mode}
            onValueChange={(mode) => onChange({ ...value, mode: mode as LateCancellationMode })}
          >
            <SelectTrigger
              className="max-w-md"
              aria-label={t("activities.cancellationRule.afterDeadline")}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="block">{t("activities.cancellationRule.block")}</SelectItem>
              <SelectItem value="allow_no_refund">
                {t("activities.cancellationRule.allowNoRefund")}
              </SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            {t("activities.cancellationRule.beforeDeadline")}
          </p>
        </div>
      )}
    </div>
  );
}

/** "2 hours", "30 minutes": the deadline in the largest unit that divides it evenly. */
export function describeDeadline(
  t: (key: string, values?: Record<string, number>) => string,
  minutes: number
): string {
  if (minutes > 0 && minutes % 1440 === 0)
    return t("activities.cancellationRule.amountDays", { count: minutes / 1440 });
  if (minutes > 0 && minutes % 60 === 0)
    return t("activities.cancellationRule.amountHours", { count: minutes / 60 });
  return t("activities.cancellationRule.amountMinutes", { count: minutes });
}

/** What an activity tells a member about cancelling: the deadline and what follows it (#638). */
export function describeActivityTerms(
  t: (key: string, values?: Record<string, number>) => string,
  activity: {
    allow_self_cancellation: boolean;
    self_cancellation_deadline_minutes: number | null;
    late_cancellation_mode: string;
  }
): string {
  if (!activity.allow_self_cancellation) return t("activities.cancellationRule.notAllowed");
  if (activity.self_cancellation_deadline_minutes == null)
    return t("activities.cancellationRule.noDeadline");
  return (
    describeDeadline(t, activity.self_cancellation_deadline_minutes) +
    " · " +
    t(
      activity.late_cancellation_mode === "allow_no_refund"
        ? "activities.cancellationRule.readAllowNoRefund"
        : "activities.cancellationRule.readBlock"
    )
  );
}
