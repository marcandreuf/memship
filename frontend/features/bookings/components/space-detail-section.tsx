"use client";

import { useTranslations } from "next-intl";
import { DetailSection } from "@/components/entity/detail-section";
import type { Space } from "../services/bookings-api";

interface SpaceDetailSectionProps {
  space: Space;
}

export function SpaceDetailSection({ space }: SpaceDetailSectionProps) {
  const t = useTranslations();

  const fields = [
    { label: t("bookings.spaces.name"), value: space.name, inline: true },
    { label: t("bookings.spaces.type"), value: space.space_type, inline: true },
    {
      label: t("bookings.spaces.hours"),
      value: `${space.open_time.slice(0, 5)}–${space.close_time.slice(0, 5)}`,
      inline: true,
    },
    {
      label: t("bookings.spaces.status"),
      value: space.is_active
        ? t("bookings.spaces.active")
        : t("bookings.spaces.inactive"),
      inline: true,
    },
    { label: t("bookings.spaces.description"), value: space.description },
  ];

  return <DetailSection fields={fields} columns={2} />;
}
