"use client";

import { useTranslations } from "next-intl";
import { DetailSection } from "@/components/entity/detail-section";
import { useMembershipTypes } from "@/features/members/hooks/use-members";
import { usePermissions } from "@/features/auth/hooks/use-permissions";
import { usePaymentOptions } from "../hooks/use-activities";
import type { ActivityData } from "../services/activities-api";
import { useLocaleDate } from "@/hooks/use-locale-date";

interface ActivityDetailSectionProps {
  activity: ActivityData;
}

export function ActivityDetailSection({ activity }: ActivityDetailSectionProps) {
  const { shortDateTime: formatDate } = useLocaleDate();
  const t = useTranslations();
  const { data: membershipTypes } = useMembershipTypes();
  const { has } = usePermissions();
  const newFlow = activity.payment_flow !== "legacy";
  // The club's default, so "As the club" says what that means today.
  const { data: options } = usePaymentOptions(newFlow && has("activities.write"));
  const clubSetting = options
    ? options.auto_cancel_enabled
      ? t("activities.payment.clubOn", { hours: options.auto_cancel_hours })
      : t("activities.payment.clubOff")
    : null;
  const autoCancelValue =
    activity.auto_cancel_enabled == null
      ? clubSetting
        ? t("activities.payment.autoCancelInherit", { setting: clubSetting })
        : t("activities.payment.autoCancelClub")
      : activity.auto_cancel_enabled
        ? [
            t("activities.payment.autoCancelOn"),
            activity.auto_cancel_hours
              ? `${activity.auto_cancel_hours} h`
              : options && t("activities.payment.hoursFromClub", { hours: options.auto_cancel_hours }),
          ]
            .filter(Boolean)
            .join(" · ")
        : t("activities.payment.autoCancelOff");

  const allowedTypes = activity.allowed_membership_types ?? [];
  const allowedTypeNames = allowedTypes
    .map((id) => membershipTypes?.find((mt) => mt.id === id)?.name ?? String(id))
    .join(", ");

  const fields = [
    { label: t("activities.name"), value: activity.name },
    { label: t("activities.slug"), value: activity.slug },
    { label: t("activities.shortDescription"), value: activity.short_description },
    { label: t("activities.startsAt"), value: formatDate(activity.starts_at) },
    { label: t("activities.endsAt"), value: formatDate(activity.ends_at) },
    { label: t("activities.registrationStartsAt"), value: formatDate(activity.registration_starts_at) },
    { label: t("activities.registrationEndsAt"), value: formatDate(activity.registration_ends_at) },
    { label: t("activities.location"), value: activity.location },
    { label: t("activities.locationDetails"), value: activity.location_details },
    { label: t("activities.minParticipants"), value: activity.min_participants, inline: true },
    { label: t("activities.maxParticipants"), value: activity.max_participants, inline: true },
    { label: t("activities.capacity"), value: `${activity.current_participants}/${activity.max_participants}`, inline: true },
    { label: t("activities.minAge"), value: activity.min_age, inline: true },
    { label: t("activities.maxAge"), value: activity.max_age, inline: true },
    { label: t("activities.taxRate"), value: `${activity.tax_rate}%`, inline: true },
    {
      label: t("activities.allowedTypes"),
      value: allowedTypes.length ? allowedTypeNames : t("activities.allowedTypesOpen"),
      inline: true,
    },
    { label: t("activities.allowSelfCancellation"), value: activity.allow_self_cancellation ? t("common.yes") : t("common.no"), inline: true },
    { label: t("activities.waitingList"), value: activity.features?.waiting_list === true ? t("common.yes") : t("common.no"), inline: true },
    ...(!newFlow
      ? []
      : [
          {
            label: t("activities.payment.methods"),
            value: activity.payment_methods
              .map((m) => t(`activities.payment.method.${m}`))
              .join(", "),
            inline: true,
          },
          {
            label: t("activities.payment.autoCancel"),
            value: autoCancelValue,
            inline: true,
          },
        ]),
  ];

  return (
    <div className="min-w-0">
      <DetailSection fields={fields} columns={3} />
      {activity.description && (
        <div className="mt-2">
          <dt className="text-xs text-muted-foreground">{t("activities.description")}</dt>
          <dd className="mt-0.5 text-sm whitespace-pre-wrap">{activity.description}</dd>
        </div>
      )}
    </div>
  );
}
