"use client";

import { useTranslations } from "next-intl";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { useMember, useUpdateMember } from "@/features/members/hooks/use-members";
import { MemberForm } from "@/features/members/components/member-form";

export default function ProfilePage() {
  const t = useTranslations();
  const { user } = useAuth();
  const { data: member, isLoading } = useMember(user?.member_id || 0);
  const { mutateAsync: update, isPending } = useUpdateMember();

  if (isLoading || !member) {
    return (
      <div className="py-8 text-center text-muted-foreground">
        {t("common.loading")}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">{t("nav.profile")}</h1>
        <Badge>{t(`status.${member.status}`)}</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-muted-foreground">
            {t("members.memberInfo")}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-1 text-sm">
          <p>
            {t("members.memberNumber")}: <span className="font-mono">{member.member_number}</span>
          </p>
          {member.membership_type_name && (
            <p>
              {t("members.membershipType")}: {member.membership_type_name}
            </p>
          )}
          <p>
            {t("members.joinedAt")}: {new Date(member.joined_at).toLocaleDateString()}
          </p>
        </CardContent>
      </Card>

      <MemberForm
        member={member}
        onSubmit={async (data) => {
          await update({
            id: member.id,
            data: {
              first_name: data.first_name,
              last_name: data.last_name,
              email: data.email || undefined,
              date_of_birth: data.date_of_birth || undefined,
              gender: data.gender || undefined,
              national_id: data.national_id || undefined,
            },
          });
        }}
        isSubmitting={isPending}
      />
    </div>
  );
}
