"use client";

import { use, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/lib/i18n/routing";
import { Button } from "@/components/ui/button";
import { DetailHeader } from "@/components/entity/detail-header";
import { InlineEditWrapper } from "@/components/entity/inline-edit-wrapper";
import { EntityTabs } from "@/components/entity/entity-tabs";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { toast } from "sonner";
import { useGroup, useDeleteGroup } from "@/features/groups/hooks/use-groups";
import { GroupDetailSection } from "@/features/groups/components/group-detail-section";
import { GroupEditForm } from "@/features/groups/components/group-edit-form";
import { MembershipTypesTab } from "@/features/groups/components/membership-types-tab";
import { MembersTab } from "@/features/groups/components/members-tab";

export default function GroupDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const groupId = Number(id);
  const t = useTranslations();
  const router = useRouter();
  const { data: group, isLoading } = useGroup(groupId);
  const { mutateAsync: remove } = useDeleteGroup();
  const [isEditing, setIsEditing] = useState(false);
  const [confirmDialog, confirmAction] = useConfirmDialog();

  if (isLoading) {
    return <div className="py-8 text-center text-muted-foreground">{t("common.loading")}</div>;
  }

  if (!group) {
    return <div className="py-8 text-center text-muted-foreground">{t("common.notFound")}</div>;
  }

  return (
    <div className="space-y-4">
      <DetailHeader
        breadcrumbs={[
          { label: t("groups.title"), href: "/groups" },
          { label: group.name },
        ]}
        title={group.name}
        actions={
          !isEditing ? (
            <>
              {confirmDialog}
              <Button
                variant="destructive"
                size="sm"
                onClick={() => {
                  confirmAction({
                    title: t("groups.deleteConfirm"),
                    cancelLabel: t("common.cancel"),
                    confirmLabel: t("common.delete"),
                    onConfirm: async () => {
                      try {
                        await remove(group.id);
                        toast.success(t("toast.success.deleted"));
                        router.push("/groups");
                      } catch { /* global handler shows error toast */ }
                    },
                  });
                }}
              >
                {t("common.delete")}
              </Button>
            </>
          ) : undefined
        }
      />

      <InlineEditWrapper
        title={t("common.details")}
        isEditing={isEditing}
        onEdit={() => setIsEditing(true)}
        onCancel={() => setIsEditing(false)}
        readContent={<GroupDetailSection group={group} />}
        editContent={
          <GroupEditForm
            group={group}
            onSuccess={() => setIsEditing(false)}
            onCancel={() => setIsEditing(false)}
          />
        }
      />

      <EntityTabs
        tabs={[
          {
            id: "membership-types",
            label: t("groups.membershipTypes"),
            content: <MembershipTypesTab groupId={groupId} />,
          },
          {
            id: "members",
            label: t("groups.members"),
            content: <MembersTab groupId={groupId} />,
          },
        ]}
      />
    </div>
  );
}
