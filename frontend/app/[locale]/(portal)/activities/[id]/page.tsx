"use client";

import { use, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/lib/i18n/routing";
import { Button } from "@/components/ui/button";
import { DetailHeader } from "@/components/entity/detail-header";
import { InlineEditWrapper } from "@/components/entity/inline-edit-wrapper";
import { EntityTabs } from "@/components/entity/entity-tabs";
import { Link } from "@/lib/i18n/routing";
import { RegistrationsTab } from "@/features/activities/components/registrations-tab";
import { ACTIVITY_STATUS_VARIANTS } from "@/lib/status-variants";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { toast } from "sonner";
import { useAuth } from "@/features/auth/hooks/use-auth";
import {
  useActivity,
  useUpdateActivity,
  useDeleteActivity,
  usePublishActivity,
  useArchiveActivity,
  useCancelActivity,
} from "@/features/activities/hooks/use-activities";
import { useEligibility, useMyRegistrations } from "@/features/activities/hooks/use-registrations";
import { ActivityDetailSection } from "@/features/activities/components/activity-detail-section";
import { ActivityEditForm } from "@/features/activities/components/activity-edit-form";
import { ModalitiesTab } from "@/features/activities/components/modalities-tab";
import { PricesTab } from "@/features/activities/components/prices-tab";
import { DiscountCodesTab } from "@/features/activities/components/discount-codes-tab";
import { ConsentsTab } from "@/features/activities/components/consents-tab";
import { AttachmentTypesTab } from "@/features/activities/components/attachment-types-tab";
import { MemberRegistrationCard } from "@/features/activities/components/member-registration-card";
import { MemberActivitySummary } from "@/features/activities/components/member-activity-summary";
import { MemberActivityDetailsTab } from "@/features/activities/components/member-activity-details-tab";
import { DetailSkeleton } from "@/components/ui/skeletons";

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
  const { data: eligibility } = useEligibility(activityId);
  const { data: myRegs } = useMyRegistrations();
  const updateMutation = useUpdateActivity();
  const deleteMutation = useDeleteActivity();
  const publishMutation = usePublishActivity();
  const archiveMutation = useArchiveActivity();
  const cancelMutation = useCancelActivity();
  const myRegistration = !isAdmin
    ? myRegs?.items?.find((r) => r.activity_id === activityId)
    : undefined;
  const isActiveRegistration = myRegistration && myRegistration.status !== "cancelled";
  const isCancelledRegistration = myRegistration && myRegistration.status === "cancelled";

  const [isEditing, setIsEditing] = useState(false);
  const [confirmDialog, confirmAction] = useConfirmDialog();

  if (isLoading) {
    return <DetailSkeleton />;
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
              {confirmDialog}
              {activity.status === "draft" && (
                <Button
                  size="sm"
                  onClick={() => {
                    confirmAction({
                      title: t("activities.actions.confirmPublish"),
                      cancelLabel: t("common.cancel"),
                      confirmLabel: t("activities.actions.publish"),
                      variant: "default",
                      onConfirm: async () => {
                        try {
                          await publishMutation.mutateAsync(activityId);
                          toast.success(t("toast.success.updated"));
                        } catch { /* global handler shows error toast */ }
                      },
                    });
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
                  onClick={() => {
                    confirmAction({
                      title: t("activities.actions.confirmArchive"),
                      cancelLabel: t("common.cancel"),
                      confirmLabel: t("activities.actions.archive"),
                      onConfirm: async () => {
                        try {
                          await archiveMutation.mutateAsync(activityId);
                          toast.success(t("toast.success.updated"));
                        } catch { /* global handler shows error toast */ }
                      },
                    });
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
                  onClick={() => {
                    confirmAction({
                      title: t("activities.actions.confirmCancel"),
                      cancelLabel: t("common.cancel"),
                      confirmLabel: t("activities.actions.cancel"),
                      onConfirm: async () => {
                        try {
                          await cancelMutation.mutateAsync(activityId);
                          toast.success(t("toast.success.updated"));
                        } catch { /* global handler shows error toast */ }
                      },
                    });
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
                  onClick={() => {
                    confirmAction({
                      title: t("activities.actions.confirmDelete"),
                      cancelLabel: t("common.cancel"),
                      confirmLabel: t("common.delete"),
                      onConfirm: async () => {
                        try {
                          await deleteMutation.mutateAsync(activityId);
                          toast.success(t("toast.success.deleted"));
                          router.push("/activities");
                        } catch { /* global handler shows error toast */ }
                      },
                    });
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

      {isAdmin ? (
        <InlineEditWrapper
          title={t("activities.basicInfo")}
          isEditing={isEditing}
          onEdit={() => setIsEditing(true)}
          onCancel={() => setIsEditing(false)}
          canEdit={isAdmin}
          readContent={<ActivityDetailSection activity={activity} showCoverImage />}
          editContent={
            <ActivityEditForm
              activity={activity}
              onSubmit={async (data) => {
                try {
                  await updateMutation.mutateAsync({ id: activityId, data });
                  toast.success(t("toast.success.saved"));
                  setIsEditing(false);
                } catch { /* global handler shows error toast */ }
              }}
              isPending={updateMutation.isPending}
              onCancel={() => setIsEditing(false)}
            />
          }
        />
      ) : (
        <MemberActivitySummary activity={activity} />
      )}

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
          ...(isAdmin
            ? [
                {
                  id: "registrations",
                  label: t("activities.registrations"),
                  content: <RegistrationsTab activityId={activityId} />,
                },
                {
                  id: "discounts",
                  label: t("activities.discounts.title"),
                  content: <DiscountCodesTab activityId={activityId} />,
                },
                {
                  id: "consents",
                  label: t("activities.consents.title"),
                  content: <ConsentsTab activityId={activityId} />,
                },
                {
                  id: "attachments",
                  label: t("activities.attachments.title"),
                  content: <AttachmentTypesTab activityId={activityId} />,
                },
              ]
            : [
                {
                  id: "details",
                  label: t("activities.details"),
                  content: <MemberActivityDetailsTab activity={activity} />,
                },
              ]),
          ...(!isAdmin && activity.status === "published"
            ? [
                {
                  id: "register",
                  label: isActiveRegistration
                    ? t("activities.registration.registered")
                    : t("activities.registration.register"),
                  content: isActiveRegistration ? (
                    <MemberRegistrationCard
                      registration={myRegistration!}
                      activity={activity}
                    />
                  ) : (
                    <div className="space-y-4">
                      {isCancelledRegistration && (
                        <MemberRegistrationCard
                          registration={myRegistration!}
                          activity={activity}
                        />
                      )}
                      <div className="py-4">
                        {activity.is_registration_open ? (
                          <Link href={`/activities/${activityId}/register`}>
                            <Button>{t("activities.registration.register")}</Button>
                          </Link>
                        ) : (
                          <Button disabled>
                            {t("activities.registration.register")}
                          </Button>
                        )}
                      </div>
                    </div>
                  ),
                },
              ]
            : []),
        ]}
      />
    </div>
  );
}
