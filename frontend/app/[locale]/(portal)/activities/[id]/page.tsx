"use client";

import { use, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/lib/i18n/routing";
import { Button } from "@/components/ui/button";
import { DetailHeader } from "@/components/entity/detail-header";
import { InlineEditWrapper } from "@/components/entity/inline-edit-wrapper";
import { EntityTabs } from "@/components/entity/entity-tabs";
import { PlaceholderTab } from "@/components/entity/placeholder-tab";
import { ACTIVITY_STATUS_VARIANTS } from "@/lib/status-variants";
import { useAuth } from "@/features/auth/hooks/use-auth";
import {
  useActivity,
  useUpdateActivity,
  useDeleteActivity,
  usePublishActivity,
  useArchiveActivity,
  useCancelActivity,
} from "@/features/activities/hooks/use-activities";
import { ActivityDetailSection } from "@/features/activities/components/activity-detail-section";
import { ActivityEditForm } from "@/features/activities/components/activity-edit-form";
import { ModalitiesTab } from "@/features/activities/components/modalities-tab";
import { PricesTab } from "@/features/activities/components/prices-tab";

export default function ActivityDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const activityId = Number(id);
  const t = useTranslations();
  const router = useRouter();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin" || user?.role === "super_admin";

  const { data: activity, isLoading } = useActivity(activityId);
  const updateMutation = useUpdateActivity();
  const deleteMutation = useDeleteActivity();
  const publishMutation = usePublishActivity();
  const archiveMutation = useArchiveActivity();
  const cancelMutation = useCancelActivity();

  const [isEditing, setIsEditing] = useState(false);

  if (isLoading) {
    return <div className="py-8 text-center text-muted-foreground">{t("common.loading")}</div>;
  }

  if (!activity) {
    return <div className="py-8 text-center text-muted-foreground">{t("common.notFound")}</div>;
  }

  return (
    <div className="space-y-4">
      <DetailHeader
        breadcrumbs={[
          { label: t("activities.title"), href: "/activities" },
          { label: activity.name },
        ]}
        title={activity.name}
        badge={{
          label: t(`activities.status.${activity.status}`),
          variant: ACTIVITY_STATUS_VARIANTS[activity.status] || "outline",
        }}
        actions={
          isAdmin ? (
            <>
              {activity.status === "draft" && (
                <Button
                  size="sm"
                  onClick={async () => {
                    if (confirm(t("activities.actions.confirmPublish"))) {
                      await publishMutation.mutateAsync(activityId);
                    }
                  }}
                  disabled={publishMutation.isPending}
                >
                  {t("activities.actions.publish")}
                </Button>
              )}
              {activity.status === "published" && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={async () => {
                    if (confirm(t("activities.actions.confirmArchive"))) {
                      await archiveMutation.mutateAsync(activityId);
                    }
                  }}
                  disabled={archiveMutation.isPending}
                >
                  {t("activities.actions.archive")}
                </Button>
              )}
              {(activity.status === "draft" || activity.status === "published") && (
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={async () => {
                    if (confirm(t("activities.actions.confirmCancel"))) {
                      await cancelMutation.mutateAsync(activityId);
                    }
                  }}
                  disabled={cancelMutation.isPending}
                >
                  {t("activities.actions.cancel")}
                </Button>
              )}
              {activity.status === "draft" && (
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={async () => {
                    if (confirm(t("activities.actions.confirmDelete"))) {
                      await deleteMutation.mutateAsync(activityId);
                      router.push("/activities");
                    }
                  }}
                  disabled={deleteMutation.isPending}
                >
                  {t("common.delete")}
                </Button>
              )}
            </>
          ) : undefined
        }
      />

      <InlineEditWrapper
        title={t("activities.basicInfo")}
        isEditing={isEditing}
        onEdit={() => setIsEditing(true)}
        onCancel={() => setIsEditing(false)}
        canEdit={isAdmin}
        readContent={<ActivityDetailSection activity={activity} />}
        editContent={
          <ActivityEditForm
            activity={activity}
            onSubmit={async (data) => {
              await updateMutation.mutateAsync({ id: activityId, data });
              setIsEditing(false);
            }}
            isPending={updateMutation.isPending}
            onCancel={() => setIsEditing(false)}
          />
        }
      />

      <EntityTabs
        tabs={[
          ...(isAdmin
            ? [
                {
                  id: "modalities",
                  label: t("activities.modalities.title"),
                  badge: activity.modalities.length,
                  content: (
                    <ModalitiesTab
                      activityId={activityId}
                      modalities={activity.modalities}
                      activity={activity}
                    />
                  ),
                },
              ]
            : []),
          {
            id: "prices",
            label: t("activities.prices.title"),
            badge: activity.prices.length,
            content: (
              <PricesTab
                activityId={activityId}
                prices={activity.prices}
                modalities={activity.modalities}
                activity={activity}
                isAdmin={isAdmin}
              />
            ),
          },
          {
            id: "registrations",
            label: t("activities.registrations"),
            content: <PlaceholderTab message={t("common.comingSoon")} />,
          },
        ]}
      />
    </div>
  );
}
