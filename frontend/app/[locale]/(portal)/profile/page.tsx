"use client";

import { useTranslations } from "next-intl";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { useMember } from "@/features/members/hooks/use-members";

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null;
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm">{value}</dd>
    </div>
  );
}

export default function ProfilePage() {
  const t = useTranslations();
  const { user } = useAuth();
  const { data: member, isLoading } = useMember(user?.member_id || 0);

  if (isLoading || !member) {
    return (
      <div className="py-8 text-center text-muted-foreground">
        {t("common.loading")}
      </div>
    );
  }

  const person = member.person;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">{t("nav.profile")}</h1>
        <Badge>{t(`status.${member.status}`)}</Badge>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{t("profile.personalInfo")}</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid gap-3 sm:grid-cols-2">
              <Field label={t("profile.firstName")} value={person.first_name} />
              <Field label={t("profile.lastName")} value={person.last_name} />
              <Field label={t("profile.email")} value={person.email} />
              <Field label={t("profile.dateOfBirth")} value={person.date_of_birth ? new Date(person.date_of_birth).toLocaleDateString() : null} />
              <Field label={t("profile.gender")} value={person.gender} />
              <Field label={t("profile.nationalId")} value={person.national_id} />
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{t("profile.membership")}</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid gap-3 sm:grid-cols-2">
              <Field label={t("profile.memberNumber")} value={member.member_number} />
              <Field label={t("profile.membershipType")} value={member.membership_type_name} />
              <Field label={t("profile.status")} value={t(`status.${member.status}`)} />
              <Field label={t("profile.joinedAt")} value={new Date(member.joined_at).toLocaleDateString()} />
            </dl>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
