"use client";

import { useTranslations, useLocale } from "next-intl";
import { DetailSection } from "@/components/entity/detail-section";
import { useSettings } from "@/features/settings/hooks/use-settings";
import type { MemberData } from "../services/members-api";
import type { GenderOption } from "@/features/settings/components/gender-options-settings";

interface MemberDetailSectionProps {
  member: MemberData;
}

function getGenderLabel(value: string | null | undefined, options: GenderOption[], locale: string): string | null | undefined {
  if (!value) return value;
  const opt = options.find((o) => o.value === value);
  if (!opt) return value;
  const key = `label_${locale}` as keyof GenderOption;
  return opt[key] || opt.label_en;
}

export function MemberDetailSection({ member }: MemberDetailSectionProps) {
  const t = useTranslations();
  const locale = useLocale();
  const { data: settings } = useSettings();
  const genderOptions = (settings?.features?.gender_options as GenderOption[] | undefined) || [];

  const fields = [
    { label: t("members.memberNumber"), value: member.member_number, inline: true },
    {
      label: t("members.name"),
      value: `${member.person.first_name} ${member.person.last_name}`,
      inline: true,
    },
    { label: t("auth.email"), value: member.person.email },
    { label: t("members.dateOfBirth"), value: member.person.date_of_birth, inline: true },
    { label: t("members.nationalId"), value: member.person.national_id, inline: true },
    { label: t("members.gender"), value: getGenderLabel(member.person.gender, genderOptions, locale), inline: true },
    { label: t("members.membershipType"), value: member.membership_type_name, inline: true },
    { label: t("common.status"), value: t(`status.${member.status}`), inline: true },
    { label: t("members.joinedAt"), value: member.joined_at, inline: true },
    { label: t("members.internalNotes"), value: member.internal_notes },
  ];

  return <DetailSection fields={fields} columns={2} />;
}
