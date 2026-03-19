"use client";

import { useTranslations } from "next-intl";
import { DetailSection } from "@/components/entity/detail-section";
import type { MemberData } from "../services/members-api";

interface MemberDetailSectionProps {
  member: MemberData;
}

export function MemberDetailSection({ member }: MemberDetailSectionProps) {
  const t = useTranslations();

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
    { label: t("members.gender"), value: member.person.gender, inline: true },
    { label: t("members.membershipType"), value: member.membership_type_name, inline: true },
    { label: t("common.status"), value: t(`status.${member.status}`), inline: true },
    { label: t("members.joinedAt"), value: member.joined_at, inline: true },
    { label: t("members.internalNotes"), value: member.internal_notes },
  ];

  return <DetailSection fields={fields} columns={2} />;
}
