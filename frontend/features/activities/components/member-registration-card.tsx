"use client";

import { useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Link } from "@/lib/i18n/routing";
import { REGISTRATION_STATUS_VARIANTS } from "@/lib/status-variants";
import { useAttachmentTypes } from "../hooks/use-activities";
import { useRegistrationAttachments, useUploadAttachment } from "../hooks/use-registrations";
import type { RegistrationData } from "../services/registrations-api";
import type { ActivityData } from "../services/activities-api";

interface MemberRegistrationCardProps {
  registration: RegistrationData;
  activity: ActivityData;
}

export function MemberRegistrationCard({ registration, activity }: MemberRegistrationCardProps) {
  const t = useTranslations();
  const isActive = registration.status !== "cancelled";
  const isCancelled = registration.status === "cancelled";

  return (
    <Card className="mt-2">
      <CardContent className="py-3 px-4 space-y-3">
        {/* Status badge */}
        <div className="flex items-center gap-3">
          <Badge variant={REGISTRATION_STATUS_VARIANTS[registration.status] || "outline"}>
            {t(`activities.registration.status.${registration.status}`)}
          </Badge>
          {isActive && (
            <span className="text-sm text-muted-foreground">
              {t("activities.registration.alreadyRegistered")}
            </span>
          )}
        </div>

        {/* Registration details grid */}
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          <span className="text-muted-foreground">{t("activities.registration.date")}</span>
          <span>{new Date(registration.created_at).toLocaleString()}</span>

          {registration.modality_id && (
            <>
              <span className="text-muted-foreground">{t("activities.modalities.title")}</span>
              <span>{activity.modalities.find((m) => m.id === registration.modality_id)?.name || "-"}</span>
            </>
          )}

          {registration.price_id && (
            <>
              <span className="text-muted-foreground">{t("activities.prices.title")}</span>
              <span>{activity.prices.find((p) => p.id === registration.price_id)?.name || "-"}</span>
            </>
          )}

          {/* Amount with discount info */}
          {registration.original_amount != null && (
            <>
              <span className="text-muted-foreground">{t("activities.registration.amount")}</span>
              <span>
                {registration.discount_code_id && registration.discounted_amount != null && registration.discounted_amount < registration.original_amount ? (
                  <>
                    <span className="line-through text-muted-foreground mr-1">
                      {Number(registration.original_amount).toFixed(2)} EUR
                    </span>
                    <span className="font-medium text-green-600">
                      {Number(registration.discounted_amount).toFixed(2)} EUR
                    </span>
                  </>
                ) : (
                  <span>{Number(registration.original_amount).toFixed(2)} EUR</span>
                )}
              </span>
            </>
          )}

          {registration.member_notes && (
            <>
              <span className="text-muted-foreground">{t("activities.registration.notes")}</span>
              <span>{registration.member_notes}</span>
            </>
          )}

          {isCancelled && registration.cancelled_at && (
            <>
              <span className="text-muted-foreground">{t("activities.registration.cancelledOn")}</span>
              <span>{new Date(registration.cancelled_at).toLocaleString()}</span>
            </>
          )}
          {isCancelled && registration.cancelled_by_name && (
            <>
              <span className="text-muted-foreground">{t("activities.registration.cancelledBy")}</span>
              <span>{registration.cancelled_by_name}</span>
            </>
          )}
          {isCancelled && registration.cancelled_reason && (
            <>
              <span className="text-muted-foreground">{t("activities.registration.cancelRegistration")}</span>
              <span>{registration.cancelled_reason}</span>
            </>
          )}
        </div>

        {/* Attachments section for active registrations */}
        {isActive && (
          <AttachmentSection
            registrationId={registration.id}
            activityId={activity.id}
          />
        )}

        <Link href="/my-activities">
          <Button variant="outline" size="sm">
            {t("activities.registration.viewMyActivities")}
          </Button>
        </Link>
      </CardContent>
    </Card>
  );
}

function AttachmentSection({
  registrationId,
  activityId,
}: {
  registrationId: number;
  activityId: number;
}) {
  const t = useTranslations();
  const { data: attachmentTypes = [] } = useAttachmentTypes(activityId);
  const { data: uploaded = [] } = useRegistrationAttachments(registrationId);
  const uploadMutation = useUploadAttachment();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadingTypeId, setUploadingTypeId] = useState<number | null>(null);

  if (attachmentTypes.length === 0) return null;

  async function handleUpload(file: File, typeId?: number) {
    setUploadingTypeId(typeId ?? null);
    try {
      await uploadMutation.mutateAsync({
        registrationId,
        file,
        attachmentTypeId: typeId,
      });
    } finally {
      setUploadingTypeId(null);
    }
  }

  return (
    <div className="border-t pt-3 space-y-2">
      <p className="text-xs font-medium text-muted-foreground">{t("activities.attachments.title")}</p>
      {attachmentTypes.map((at) => {
        const existing = uploaded.find((u) => u.attachment_type_id === at.id);
        return (
          <div key={at.id} className="flex items-center gap-3 text-sm">
            <div className="flex-1">
              <span className="font-medium">{at.name}</span>
              {at.is_mandatory && <span className="text-destructive ml-1">*</span>}
              {at.allowed_extensions?.length > 0 && (
                <span className="text-muted-foreground ml-1 text-xs">
                  ({at.allowed_extensions.join(", ")})
                </span>
              )}
            </div>
            {existing ? (
              <Badge variant="secondary" className="text-xs">{existing.file_name}</Badge>
            ) : (
              <>
                <Input
                  ref={fileInputRef}
                  type="file"
                  className="max-w-48 h-8 text-xs"
                  accept={at.allowed_extensions?.length ? at.allowed_extensions.map((e) => `.${e}`).join(",") : undefined}
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (file) await handleUpload(file, at.id);
                    e.target.value = "";
                  }}
                  disabled={uploadMutation.isPending && uploadingTypeId === at.id}
                />
              </>
            )}
          </div>
        );
      })}
      {uploadMutation.isError && (
        <p className="text-xs text-destructive">
          {(uploadMutation.error as Error)?.message || t("activities.attachments.uploadFailed")}
        </p>
      )}
    </div>
  );
}
