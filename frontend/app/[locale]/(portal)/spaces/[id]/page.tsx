"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { useRouter } from "@/lib/i18n/routing";
import { Button } from "@/components/ui/button";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { DetailHeader } from "@/components/entity/detail-header";
import { InlineEditWrapper } from "@/components/entity/inline-edit-wrapper";
import { EntityTabs } from "@/components/entity/entity-tabs";
import { DetailSkeleton } from "@/components/ui/skeletons";
import { useQueryClient } from "@tanstack/react-query";
import { ClientApiError } from "@/lib/client-api";
import { useDeleteSpace, useSlots, useSpace } from "@/features/bookings/hooks/use-bookings";
import { deleteSpace as deleteSpaceApi } from "@/features/bookings/services/bookings-api";
import { SpaceForm } from "@/features/bookings/components/space-form";
import { SpaceDetailSection } from "@/features/bookings/components/space-detail-section";
import { SlotsTab } from "@/features/bookings/components/slots-tab";
import { SpaceBookingsTab } from "@/features/bookings/components/space-bookings-tab";
import { usePermissions } from "@/features/auth/hooks/use-permissions";

export default function SpaceDetailPage() {
  const t = useTranslations();
  const { has } = usePermissions();
  const canWrite = has("bookings.write");
  const params = useParams();
  const router = useRouter();
  const id = Number(params.id);
  const { data: space, isLoading } = useSpace(id);
  // Read from the same cache the slots tab fills, purely for the tab's count
  // badge — the tab itself owns the fetch.
  const { data: slots } = useSlots(id);
  const [isEditing, setIsEditing] = useState(false);
  const qc = useQueryClient();
  const deleteMutation = useDeleteSpace();
  const [confirmDialog, confirmAction] = useConfirmDialog();

  // Delete is the explicit destructive path (deactivation lives in the edit
  // form). The first attempt goes through the raw API call so the expected 409
  // skips the global error toast; it carries the affected-member count —
  // confirm it, then force.
  async function onDelete() {
    try {
      await deleteSpaceApi(id);
      qc.invalidateQueries({ queryKey: ["spaces"] });
      toast.success(t("toast.success.deleted"));
      router.push("/spaces");
    } catch (error) {
      if (error instanceof ClientApiError && error.status === 409) {
        const affected =
          (error.detail as unknown as { affected_members?: number })
            ?.affected_members ?? 0;
        confirmAction({
          title: t("bookings.spaces.confirmDelete"),
          description: t("bookings.spaces.deleteAffected", { count: affected }),
          cancelLabel: t("common.cancel"),
          confirmLabel: t("common.delete"),
          onConfirm: async () => {
            try {
              await deleteMutation.mutateAsync({ id, force: true });
              toast.success(t("toast.success.deleted"));
              router.push("/spaces");
            } catch {
              /* global handler */
            }
          },
        });
      }
    }
  }

  if (isLoading) return <DetailSkeleton />;
  if (!space)
    return (
      <div className="py-8 text-center text-muted-foreground">
        {t("bookings.spaces.notFound")}
      </div>
    );

  return (
    <div className="space-y-4">
      <DetailHeader
        breadcrumbs={[
          { label: t("bookings.spaces.title"), href: "/spaces" },
          { label: space.name },
        ]}
        title={space.name}
        badge={{
          label: space.is_active
            ? t("bookings.spaces.active")
            : t("bookings.spaces.inactive"),
          variant: space.is_active ? "default" : "secondary",
        }}
        actions={
          canWrite ? (
            <>
              {confirmDialog}
              <Button
                variant="destructive"
                size="sm"
                disabled={deleteMutation.isPending}
                onClick={() =>
                  confirmAction({
                    title: t("bookings.spaces.confirmDelete"),
                    cancelLabel: t("common.cancel"),
                    confirmLabel: t("common.delete"),
                    onConfirm: onDelete,
                  })
                }
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
        canEdit={canWrite}
        readContent={<SpaceDetailSection space={space} />}
        editContent={
          <SpaceForm
            space={space}
            onSuccess={() => setIsEditing(false)}
            onCancel={() => setIsEditing(false)}
          />
        }
      />

      <EntityTabs
        lazy
        tabs={[
          {
            id: "slots",
            label: t("bookings.slots.tab"),
            badge: slots?.length,
            content: <SlotsTab spaceId={id} />,
          },
          {
            id: "bookings",
            label: t("bookings.adminBookings.tab"),
            content: <SpaceBookingsTab spaceId={id} />,
          },
        ]}
      />
    </div>
  );
}
