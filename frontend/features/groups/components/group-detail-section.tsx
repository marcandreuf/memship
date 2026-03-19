"use client";

import { useTranslations } from "next-intl";
import { DetailSection } from "@/components/entity/detail-section";
import type { GroupData } from "../services/groups-api";

interface GroupDetailSectionProps {
  group: GroupData;
}

export function GroupDetailSection({ group }: GroupDetailSectionProps) {
  const t = useTranslations();

  const fields = [
    { label: t("groups.name"), value: group.name, inline: true },
    { label: t("groups.slug"), value: group.slug, inline: true },
    { label: t("groups.description"), value: group.description },
    {
      label: t("groups.billable"),
      value: group.is_billable ? t("common.yes") : t("common.no"),
      inline: true,
    },
    {
      label: t("groups.color"),
      value: group.color ? (
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block h-3.5 w-3.5 rounded-full border"
            style={{ backgroundColor: group.color }}
          />
          <span className="font-mono text-xs">{group.color}</span>
        </span>
      ) : null,
      inline: true,
    },
  ];

  return <DetailSection fields={fields} columns={2} />;
}
