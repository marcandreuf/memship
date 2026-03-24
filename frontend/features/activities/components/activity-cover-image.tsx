"use client";

import { useRef } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useUploadCoverImage, useDeleteCoverImage } from "../hooks/use-activities";
import type { ActivityData } from "../services/activities-api";

const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"];
const MAX_SIZE_MB = 10;

interface ActivityCoverImageProps {
  activity: ActivityData;
  isAdmin: boolean;
}

export function ActivityCoverImage({ activity, isAdmin }: ActivityCoverImageProps) {
  const t = useTranslations();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadMutation = useUploadCoverImage(activity.id);
  const deleteMutation = useDeleteCoverImage(activity.id);

  const imageUrl = activity.image_url
    ? `/api/uploads${activity.image_url.replace("/uploads", "")}?t=${new Date(activity.updated_at).getTime()}`
    : null;

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!ALLOWED_TYPES.includes(file.type)) {
      toast.error(t("activities.coverImage.invalidType"));
      return;
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      toast.error(t("activities.coverImage.maxSize", { size: MAX_SIZE_MB }));
      return;
    }

    try {
      await uploadMutation.mutateAsync(file);
      toast.success(t("toast.success.saved"));
    } catch {
      /* global handler shows error toast */
    }

    // Reset input so re-uploading the same file triggers onChange
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleDelete = async () => {
    if (!confirm(t("activities.coverImage.confirmRemove"))) return;
    try {
      await deleteMutation.mutateAsync();
      toast.success(t("toast.success.deleted"));
    } catch {
      /* global handler shows error toast */
    }
  };

  if (!imageUrl && !isAdmin) return null;

  return (
    <div className="relative">
      {imageUrl ? (
        <div className="relative overflow-hidden rounded-lg border">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imageUrl}
            alt={activity.name}
            className="w-full max-h-72 object-cover"
          />
          {isAdmin && (
            <div className="absolute top-2 right-2 flex gap-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadMutation.isPending}
              >
                {uploadMutation.isPending
                  ? t("activities.coverImage.uploading")
                  : t("activities.coverImage.upload")}
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={handleDelete}
                disabled={deleteMutation.isPending}
              >
                {t("activities.coverImage.remove")}
              </Button>
            </div>
          )}
        </div>
      ) : (
        isAdmin && (
          <div
            className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-8 text-muted-foreground cursor-pointer hover:border-primary/50 transition-colors"
            onClick={() => fileInputRef.current?.click()}
          >
            <p className="text-sm font-medium">
              {uploadMutation.isPending
                ? t("activities.coverImage.uploading")
                : t("activities.coverImage.dragOrClick")}
            </p>
            <p className="text-xs">
              {t("activities.coverImage.maxSizeHint", { size: MAX_SIZE_MB })}
            </p>
          </div>
        )
      )}

      {isAdmin && (
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          className="hidden"
          onChange={handleFileSelect}
        />
      )}
    </div>
  );
}
