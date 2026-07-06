"use client";

import { useRef } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { toast } from "sonner";
import { apiClient } from "@/lib/client-api";
import { useMutation, useQueryClient } from "@tanstack/react-query";

const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_SIZE_MB = 5;

async function uploadPhoto(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch("/api/members/me/photo", {
    method: "POST",
    body: formData,
    credentials: "include",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}

async function deletePhoto() {
  return apiClient("/members/me/photo", { method: "DELETE" });
}

function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/);
  return `${parts[0]?.[0] ?? ""}${parts.length > 1 ? parts[parts.length - 1][0] : ""}`.toUpperCase();
}

interface MemberPhotoUploadProps {
  photoUrl: string | null;
  fullName: string;
}

export function MemberPhotoUpload({ photoUrl, fullName }: MemberPhotoUploadProps) {
  const t = useTranslations();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const [confirmDialog, confirmAction] = useConfirmDialog();

  // Invalidate everything that renders the photo (card, member record, profile).
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["me", "card"] });
    queryClient.invalidateQueries({ queryKey: ["members"] });
    queryClient.invalidateQueries({ queryKey: ["my-profile"] });
    queryClient.invalidateQueries({ queryKey: ["auth"] });
  };

  const uploadMutation = useMutation({ mutationFn: uploadPhoto, onSuccess: invalidate });
  const deleteMutation = useMutation({ mutationFn: deletePhoto, onSuccess: invalidate });

  // Cache-buster so a re-upload of the same filename shows immediately.
  const imageSrc = photoUrl
    ? `/api/uploads${photoUrl.replace("/uploads", "")}?t=${Date.now()}`
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
      toast.error(t("toast.error.generic"));
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleDelete = () => {
    confirmAction({
      title: t("photo.confirmRemove"),
      cancelLabel: t("common.cancel"),
      confirmLabel: t("photo.remove"),
      onConfirm: async () => {
        try {
          await deleteMutation.mutateAsync();
          toast.success(t("toast.success.deleted"));
        } catch {
          toast.error(t("toast.error.generic"));
        }
      },
    });
  };

  return (
    <div className="flex flex-col items-center gap-2 shrink-0">
      {confirmDialog}
      <Avatar className="h-28 w-28">
        {imageSrc ? <AvatarImage src={imageSrc} alt={fullName} /> : null}
        <AvatarFallback className="text-3xl font-semibold">
          {initialsOf(fullName)}
        </AvatarFallback>
      </Avatar>
      <div className="flex gap-2">
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploadMutation.isPending}
        >
          {uploadMutation.isPending
            ? t("common.loading")
            : photoUrl
              ? t("common.change")
              : t("photo.dragOrClick")}
        </Button>
        {photoUrl && (
          <Button
            type="button"
            size="sm"
            variant="destructive"
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
          >
            {t("photo.remove")}
          </Button>
        )}
      </div>
      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={handleFileSelect}
      />
    </div>
  );
}
