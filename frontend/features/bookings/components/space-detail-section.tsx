"use client";

import { useTranslations } from "next-intl";
import { DetailSection } from "@/components/entity/detail-section";
import { useMembershipTypes } from "@/features/members/hooks/use-members";
import { useFormatters } from "@/hooks/use-formatters";
import type { Space } from "../services/bookings-api";

interface SpaceDetailSectionProps {
  space: Space;
}

export function SpaceDetailSection({ space }: SpaceDetailSectionProps) {
  const t = useTranslations();
  const { data: membershipTypes } = useMembershipTypes();
  const { formatCurrency } = useFormatters();

  const allowed = space.allowed_membership_types ?? [];
  const allowedNames = allowed
    .map(
      (id) =>
        membershipTypes?.find((mt) => mt.id === id)?.name ?? String(id)
    )
    .join(", ");

  const fields = [
    { label: t("bookings.spaces.name"), value: space.name, inline: true },
    { label: t("bookings.spaces.type"), value: space.space_type, inline: true },
    {
      label: t("bookings.spaces.hours"),
      value: `${space.open_time.slice(0, 5)}–${space.close_time.slice(0, 5)}`,
      inline: true,
    },
    {
      label: t("bookings.spaces.price"),
      value: space.price
        ? formatCurrency(space.price)
        : t("bookings.spaces.free"),
      inline: true,
    },
    {
      label: t("bookings.spaces.status"),
      value: space.is_active
        ? t("bookings.spaces.active")
        : t("bookings.spaces.inactive"),
      inline: true,
    },
    {
      label: t("bookings.spaces.allowedTypes"),
      value: allowed.length
        ? allowedNames
        : t("bookings.spaces.allowedTypesOpen"),
      inline: true,
    },
    { label: t("bookings.spaces.description"), value: space.description },
  ];

  return <DetailSection fields={fields} columns={2} />;
}
