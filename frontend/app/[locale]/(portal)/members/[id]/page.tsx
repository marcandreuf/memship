"use client";

import { use } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/lib/i18n/routing";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MemberForm } from "@/features/members/components/member-form";
import { MemberStatusActions } from "@/features/members/components/member-status-actions";
import {
  useMember,
  useUpdateMember,
  useDeleteMember,
} from "@/features/members/hooks/use-members";
import { useAuth } from "@/features/auth/hooks/use-auth";

export default function MemberDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const memberId = Number(id);
  const t = useTranslations();
  const router = useRouter();
  const { user } = useAuth();
  const { data: member, isLoading } = useMember(memberId);
  const { mutateAsync: update, isPending: isUpdating } = useUpdateMember();
  const { mutateAsync: remove } = useDeleteMember();

  const isAdmin = user?.role === "admin" || user?.role === "super_admin";

  if (isLoading) {
    return (
      <div className="py-8 text-center text-muted-foreground">
        {t("common.loading")}
      </div>
    );
  }

  if (!member) {
    return (
      <div className="py-8 text-center text-muted-foreground">
        {t("common.noResults")}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Button variant="outline" onClick={() => router.push("/members")}>
          {t("common.back")}
        </Button>
        <h1 className="text-xl font-bold">
          {member.person.first_name} {member.person.last_name}
        </h1>
        <Badge>{t(`status.${member.status}`)}</Badge>
      </div>

      {isAdmin && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{t("common.status")}</CardTitle>
          </CardHeader>
          <CardContent>
            <MemberStatusActions member={member} />
          </CardContent>
        </Card>
      )}

      <MemberForm
        member={member}
        onSubmit={async (data) => {
          await update({
            id: memberId,
            data: {
              ...data,
              email: data.email || undefined,
              date_of_birth: data.date_of_birth || undefined,
              gender: data.gender || undefined,
              national_id: data.national_id || undefined,
              internal_notes: data.internal_notes || undefined,
            },
          });
        }}
        isSubmitting={isUpdating}
      />

      {isAdmin && (
        <div className="pt-4">
          <Button
            variant="destructive"
            onClick={async () => {
              if (confirm(t("members.confirmDelete"))) {
                await remove(memberId);
                router.push("/members");
              }
            }}
          >
            {t("common.delete")}
          </Button>
        </div>
      )}
    </div>
  );
}
