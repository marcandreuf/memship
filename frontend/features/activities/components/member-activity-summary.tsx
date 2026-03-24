"use client";

import { useTranslations } from "next-intl";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ActivityData } from "../services/activities-api";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface MemberActivitySummaryProps {
  activity: ActivityData;
}

export function MemberActivitySummary({ activity }: MemberActivitySummaryProps) {
  const t = useTranslations();

  const now = new Date();
  const regStart = new Date(activity.registration_starts_at);
  const regEnd = new Date(activity.registration_ends_at);
  const isRegOpen = now >= regStart && now <= regEnd;
  const isRegNotYetOpen = now < regStart;

  const regBadgeVariant = isRegOpen ? "default" : "destructive";
  const regBadgeLabel = isRegOpen
    ? t("activities.registrationOpen")
    : isRegNotYetOpen
      ? t("activities.registrationNotYetOpen")
      : t("activities.registrationClosed");

  const hasAgeRange = activity.min_age !== null || activity.max_age !== null;

  const imageUrl = activity.image_url
    ? `/api/uploads${activity.image_url.replace("/uploads", "")}?t=${new Date(activity.updated_at).getTime()}`
    : null;

  return (
    <Card>
      <CardContent className="px-6 pt-3 pb-5">
        {/* Grid: 3 columns (50% dates | 20% info | 30% image) when image present */}
        <div className={`grid gap-x-4 gap-y-5 ${imageUrl ? "lg:grid-cols-[45%_20%_1fr]" : "lg:grid-cols-[1fr_auto]"}`}>

          {/* Row 1: short description — spans dates + info columns (or all 3 when no image) */}
          {activity.short_description && (
            <p className={`text-lg text-muted-foreground ${imageUrl ? "lg:col-span-2" : "lg:col-span-2"}`}>
              {activity.short_description}
            </p>
          )}

          {/* Row 1 right: cover image (spans 2 rows via row-span) */}
          {imageUrl && (
            <div className={`${activity.short_description ? "lg:row-span-2" : ""}`}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={imageUrl}
                alt={activity.name}
                className="w-full h-full object-cover rounded-lg"
              />
            </div>
          )}

          {/* Row 2 col 1: dates */}
          <div className="space-y-5">
            {/* Registration period */}
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <h3 className="text-base font-medium text-muted-foreground">
                  {t("activities.registrationPeriod")}
                </h3>
                <Badge variant={regBadgeVariant}>
                  {regBadgeLabel}
                </Badge>
              </div>
              <p className="text-xl font-semibold">
                {formatDateTime(activity.registration_starts_at)} — {formatDateTime(activity.registration_ends_at)}
              </p>
            </div>

            {/* Activity dates */}
            <div>
              <h3 className="text-base font-medium text-muted-foreground mb-1.5">
                {t("activities.activityDates")}
              </h3>
              <p className="text-xl font-semibold">
                {formatDate(activity.starts_at)} — {formatDate(activity.ends_at)}
              </p>
            </div>
          </div>

          {/* Row 2 col 2: key info */}
          <div className="space-y-3 text-base">
            {activity.location && (
              <div>
                <div className="text-muted-foreground text-sm">{t("activities.location")}</div>
                <div className="font-medium">{activity.location}</div>
              </div>
            )}
            <div>
              <div className="text-muted-foreground text-sm">{t("activities.capacity")}</div>
              <div className="font-medium">
                {activity.available_spots > 0
                  ? t("activities.spotsAvailable", { count: activity.available_spots })
                  : t("activities.full")}
              </div>
            </div>
            {hasAgeRange && (
              <div>
                <div className="text-muted-foreground text-sm">{t("activities.ageRange")}</div>
                <div className="font-medium">
                  {activity.min_age && activity.max_age
                    ? t("activities.ages", { min: activity.min_age, max: activity.max_age })
                    : activity.min_age
                      ? `${activity.min_age}+`
                      : `≤ ${activity.max_age}`}
                </div>
              </div>
            )}
          </div>

          {/* Row 3: description (spans all columns) */}
          {activity.description && (
            <div className={`border-t pt-5 ${imageUrl ? "lg:col-span-3" : "lg:col-span-2"}`}>
              <p className="text-base whitespace-pre-wrap">{activity.description}</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
