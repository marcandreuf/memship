"use client";

import { use, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/lib/i18n/routing";
import { Button } from "@/components/ui/button";
import { DetailHeader } from "@/components/entity/detail-header";
import { InlineEditWrapper } from "@/components/entity/inline-edit-wrapper";
import { EntityTabs } from "@/components/entity/entity-tabs";
import { PlaceholderTab } from "@/components/entity/placeholder-tab";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { DetailSkeleton } from "@/components/ui/skeletons";
import { toast } from "sonner";
import { EntityDetailSection } from "@/features/entities/components/entity-detail-section";
import { EntityForm } from "@/features/entities/components/entity-form";
import { EntityAddressTab } from "@/features/entities/components/entity-address-tab";
import { EntityContactsTab } from "@/features/entities/components/entity-contacts-tab";
import { PartyReceiptsTab } from "@/features/receipts/components/party-receipts-tab";
import {
  useDeleteEntity,
  useEntity,
  useUpdateEntity,
} from "@/features/entities/hooks/use-entities";
import { useReceipts } from "@/features/receipts/hooks/use-receipts";
import { usePermissions } from "@/features/auth/hooks/use-permissions";
import { ClientApiError } from "@/lib/client-api";

export default function EntityDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const entityId = Number(id);
  const t = useTranslations();
  const router = useRouter();
  const { data: entity, isLoading } = useEntity(entityId);
  const { mutateAsync: update, isPending: isUpdating } = useUpdateEntity();
  const deleteMutation = useDeleteEntity();
  const [isEditing, setIsEditing] = useState(false);
  const [confirmDialog, confirmAction] = useConfirmDialog();

  const { has } = usePermissions();
  const canWrite = has("entities.write");
  const canReadBilling = has("billing.read");

  // Receipt count for the tab badge
  const receiptParams = useMemo(() => {
    const p = new URLSearchParams();
    p.set("party_id", String(entityId));
    p.set("per_page", "1");
    return p;
  }, [entityId]);
  const { data: receiptData } = useReceipts(receiptParams, canReadBilling);

  if (isLoading) {
    return <DetailSkeleton />;
  }

  if (!entity) {
    return (
      <div className="py-8 text-center text-muted-foreground">
        {t("common.notFound")}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {confirmDialog}
      <DetailHeader
        breadcrumbs={[
          { label: t("entities.title"), href: "/entities" },
          { label: entity.name },
        ]}
        title={entity.name}
        badge={{
          label: t(`entities.kinds.${entity.kind}`),
          variant: "outline",
        }}
        actions={
          canWrite ? (
            <Button
              variant="destructive"
              onClick={() => {
                confirmAction({
                  title: t("entities.deleteConfirm"),
                  description: t("entities.deleteConfirmDescription"),
                  cancelLabel: t("common.cancel"),
                  confirmLabel: t("common.delete"),
                  onConfirm: async () => {
                    try {
                      await deleteMutation.mutateAsync(entityId);
                      toast.success(t("toast.success.deleted"));
                      router.push("/entities");
                    } catch (error) {
                      if (error instanceof ClientApiError && error.status === 409) {
                        toast.error(t("entities.deleteHasHistory"));
                      }
                      // Anything else is reported once by the mutation cache.
                    }
                  },
                });
              }}
              disabled={deleteMutation.isPending}
            >
              {t("common.delete")}
            </Button>
          ) : undefined
        }
      />

      <InlineEditWrapper
        title={t("entities.entityInfo")}
        isEditing={isEditing}
        onEdit={() => setIsEditing(true)}
        onCancel={() => setIsEditing(false)}
        canEdit={canWrite}
        readContent={<EntityDetailSection entity={entity} />}
        editContent={
          <EntityForm
            entity={entity}
            onSubmit={async (data) => {
              await update({
                id: entityId,
                // An emptied field is sent as null: `undefined` is dropped by
                // JSON.stringify, and the partial update then keeps the old value.
                data: {
                  ...data,
                  legal_name: data.legal_name || null,
                  national_id: data.national_id || null,
                  email: data.email || null,
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
        lazy
        tabs={[
          ...(canReadBilling
            ? [
                {
                  id: "receipts",
                  label: t("receipts.title"),
                  badge: receiptData?.meta?.total,
                  content: <PartyReceiptsTab partyId={entityId} />,
                },
              ]
            : []),
          {
            id: "address",
            label: t("entities.addressTab"),
            content: <EntityAddressTab entityId={entityId} />,
          },
          {
            id: "contacts",
            label: t("entities.contactsTab"),
            content: <EntityContactsTab partyId={entityId} />,
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
