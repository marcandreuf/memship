"use client";

import { useTranslations } from "next-intl";
import { DetailSection } from "@/components/entity/detail-section";
import type { ActivityData } from "../services/activities-api";

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface MemberActivityDetailsTabProps {
  activity: ActivityData;
}

export function MemberActivityDetailsTab({ activity }: MemberActivityDetailsTabProps) {
  const t = useTranslations();

  const fields = [
    { label: t("activities.location"), value: activity.location },
    { label: t("activities.locationDetails"), value: activity.location_details },
    { label: t("activities.startsAt"), value: formatDateTime(activity.starts_at), inline: true },
    { label: t("activities.endsAt"), value: formatDateTime(activity.ends_at), inline: true },
    { label: t("activities.registrationStartsAt"), value: formatDateTime(activity.registration_starts_at), inline: true },
    { label: t("activities.registrationEndsAt"), value: formatDateTime(activity.registration_ends_at), inline: true },
    { label: t("activities.minParticipants"), value: activity.min_participants, inline: true },
    { label: t("activities.maxParticipants"), value: activity.max_participants, inline: true },
    { label: t("activities.capacity"), value: `${activity.current_participants}/${activity.max_participants}`, inline: true },
    ...(activity.min_age !== null ? [{ label: t("activities.minAge"), value: activity.min_age, inline: true }] : []),
    ...(activity.max_age !== null ? [{ label: t("activities.maxAge"), value: activity.max_age, inline: true }] : []),
    { label: t("activities.allowSelfCancellation"), value: activity.allow_self_cancellation ? t("common.yes") : t("common.no"), inline: true },
  ];

  return <DetailSection fields={fields} columns={3} />;
}
