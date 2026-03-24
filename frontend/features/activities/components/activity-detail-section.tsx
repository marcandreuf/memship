"use client";

import { useTranslations } from "next-intl";
import { DetailSection } from "@/components/entity/detail-section";
import { ActivityCoverImage } from "./activity-cover-image";
import type { ActivityData } from "../services/activities-api";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface ActivityDetailSectionProps {
  activity: ActivityData;
  showCoverImage?: boolean;
}

export function ActivityDetailSection({ activity, showCoverImage }: ActivityDetailSectionProps) {
  const t = useTranslations();

  const fields = [
    { label: t("activities.name"), value: activity.name },
    { label: t("activities.slug"), value: activity.slug, inline: true },
    { label: t("activities.shortDescription"), value: activity.short_description },
    { label: t("activities.startsAt"), value: formatDate(activity.starts_at), inline: true },
    { label: t("activities.endsAt"), value: formatDate(activity.ends_at), inline: true },
    { label: t("activities.registrationStartsAt"), value: formatDate(activity.registration_starts_at), inline: true },
    { label: t("activities.registrationEndsAt"), value: formatDate(activity.registration_ends_at), inline: true },
    { label: t("activities.location"), value: activity.location },
    { label: t("activities.locationDetails"), value: activity.location_details },
    { label: t("activities.minParticipants"), value: activity.min_participants, inline: true },
    { label: t("activities.maxParticipants"), value: activity.max_participants, inline: true },
    { label: t("activities.capacity"), value: `${activity.current_participants}/${activity.max_participants}`, inline: true },
    { label: t("activities.minAge"), value: activity.min_age, inline: true },
    { label: t("activities.maxAge"), value: activity.max_age, inline: true },
    { label: t("activities.taxRate"), value: `${activity.tax_rate}%`, inline: true },
    { label: t("activities.allowSelfCancellation"), value: activity.allow_self_cancellation ? t("common.yes") : t("common.no"), inline: true },
  ];

  return (
    <div className="flex gap-4">
      <div className="flex-1 min-w-0">
        <DetailSection fields={fields} columns={3} />
        {activity.description && (
          <div className="mt-2">
            <dt className="text-xs text-muted-foreground">{t("activities.description")}</dt>
            <dd className="mt-0.5 text-sm whitespace-pre-wrap">{activity.description}</dd>
          </div>
        )}
      </div>
      {showCoverImage && (
        <div className="hidden lg:block w-64 shrink-0">
          <ActivityCoverImage activity={activity} isAdmin />
        </div>
      )}
    </div>
  );
}
