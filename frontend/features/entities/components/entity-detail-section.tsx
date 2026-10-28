"use client";

import { useTranslations } from "next-intl";
import { DetailSection } from "@/components/entity/detail-section";
import { useFormatters } from "@/hooks/use-formatters";
import type { EntityData } from "../services/entities-api";

interface EntityDetailSectionProps {
  entity: EntityData;
}

export function EntityDetailSection({ entity }: EntityDetailSectionProps) {
  const t = useTranslations();
  const { formatDate } = useFormatters();

  const fields = [
    { label: t("entities.name"), value: entity.name, inline: true },
    { label: t("entities.kind"), value: t(`entities.kinds.${entity.kind}`), inline: true },
    { label: t("entities.legalName"), value: entity.legal_name, inline: true },
    { label: t("entities.nationalId"), value: entity.national_id, inline: true },
    { label: t("auth.email"), value: entity.email },
    { label: t("entities.createdAt"), value: formatDate(entity.created_at), inline: true },
  ];

  return <DetailSection fields={fields} columns={2} />;
}
