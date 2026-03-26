"use client";

import { use, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { DetailHeader } from "@/components/entity/detail-header";
import { InlineEditWrapper } from "@/components/entity/inline-edit-wrapper";
import { EntityTabs } from "@/components/entity/entity-tabs";
import { PlaceholderTab } from "@/components/entity/placeholder-tab";
import { MemberActivitiesTab } from "@/features/members/components/member-activities-tab";
import { ContactInfoTab } from "@/features/members/components/contact-info-tab";
import { MemberReceiptsTab } from "@/features/members/components/member-receipts-tab";
import { MemberDetailSection } from "@/features/members/components/member-detail-section";
import { MemberForm } from "@/features/members/components/member-form";
import { MemberStatusActions } from "@/features/members/components/member-status-actions";
import {
  useMember,
  useUpdateMember,
} from "@/features/members/hooks/use-members";
import { useReceipts } from "@/features/receipts/hooks/use-receipts";
import { toast } from "sonner";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { MEMBER_STATUS_VARIANTS } from "@/lib/status-variants";
import { DetailSkeleton } from "@/components/ui/skeletons";

export default function MemberDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const memberId = Number(id);
  const t = useTranslations();
  const { user } = useAuth();
  const { data: member, isLoading } = useMember(memberId);
  const { mutateAsync: update, isPending: isUpdating } = useUpdateMember();
  const [isEditing, setIsEditing] = useState(false);

  const isAdmin = user?.role === "admin" || user?.role === "super_admin";

  // Receipt count for badge
  const receiptParams = useMemo(() => {
    const p = new URLSearchParams();
    p.set("member_id", String(memberId));
    p.set("per_page", "1");
    return p;
  }, [memberId]);
  const { data: receiptData } = useReceipts(isAdmin ? receiptParams : undefined);

  if (isLoading) {
    return <DetailSkeleton />;
  }

  if (!member) {
    return (
      <div className="py-8 text-center text-muted-foreground">
        {t("common.notFound")}
      </div>
    );
  }

  const memberName = `${member.person.first_name} ${member.person.last_name}`;

  return (
    <div className="space-y-4">
      <DetailHeader
        breadcrumbs={[
          { label: t("nav.members"), href: "/members" },
          { label: memberName },
        ]}
        title={memberName}
        badge={{
          label: t(`status.${member.status}`),
          variant: MEMBER_STATUS_VARIANTS[member.status] || "outline",
        }}
        actions={
          isAdmin ? <MemberStatusActions member={member} /> : undefined
        }
      />

      <InlineEditWrapper
        title={t("members.memberInfo")}
        isEditing={isEditing}
        onEdit={() => setIsEditing(true)}
        onCancel={() => setIsEditing(false)}
        canEdit={isAdmin}
        readContent={<MemberDetailSection member={member} />}
        editContent={
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
              toast.success(t("toast.success.saved"));
              setIsEditing(false);
            }}
            isSubmitting={isUpdating}
            onCancel={() => setIsEditing(false)}
          />
        }
      />

      <EntityTabs
        tabs={[
          {
            id: "contact",
            label: t("members.contactInfo"),
            content: <ContactInfoTab personId={member.person_id} />,
          },
          {
            id: "activities",
            label: t("members.activities"),
            content: <MemberActivitiesTab memberId={memberId} />,
          },
          {
            id: "receipts",
            label: t("receipts.title"),
            badge: receiptData?.meta?.total,
            content: <MemberReceiptsTab memberId={memberId} />,
          },
          {
            id: "audit",
            label: t("members.auditLog"),
            content: <PlaceholderTab message={t("common.comingSoon")} />,
          },
        ]}
      />
    </div>
  );
}
