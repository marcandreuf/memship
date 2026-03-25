"use client";

import { useRef } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { toast } from "sonner";
import { apiClient } from "@/lib/client-api";
import { useMutation, useQueryClient } from "@tanstack/react-query";

const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp", "image/svg+xml"];
const MAX_SIZE_MB = 5;

async function uploadLogo(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch("/api/settings/logo", {
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

async function deleteLogo() {
  return apiClient("/settings/logo", { method: "DELETE" });
}

interface LogoUploadProps {
  logoUrl: string | null;
}

export function LogoUpload({ logoUrl }: LogoUploadProps) {
  const t = useTranslations();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const [confirmDialog, confirmAction] = useConfirmDialog();

  const uploadMutation = useMutation({
    mutationFn: uploadLogo,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteLogo,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings"] }),
  });

  const imageUrl = logoUrl
    ? `/api/uploads${logoUrl.replace("/uploads", "")}?t=${Date.now()}`
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

    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleDelete = () => {
    confirmAction({
      title: t("activities.coverImage.confirmRemove"),
      cancelLabel: t("common.cancel"),
      confirmLabel: t("activities.coverImage.remove"),
      onConfirm: async () => {
        try {
          await deleteMutation.mutateAsync();
          toast.success(t("toast.success.deleted"));
        } catch {
          /* global handler shows error toast */
        }
      },
    });
  };

  return (
    <div>
      {confirmDialog}
      {imageUrl ? (
        <div className="flex items-center gap-4">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imageUrl}
            alt="Logo"
            className="h-16 w-auto max-w-48 object-contain rounded border"
          />
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadMutation.isPending}
            >
              {uploadMutation.isPending ? t("common.loading") : t("common.change")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
            >
              {t("activities.coverImage.remove")}
            </Button>
          </div>
        </div>
      ) : (
        <div
          className="flex items-center justify-center rounded-lg border border-dashed p-6 text-muted-foreground cursor-pointer hover:border-primary/50 transition-colors"
          onClick={() => fileInputRef.current?.click()}
        >
          <p className="text-sm">
            {uploadMutation.isPending
              ? t("common.loading")
              : t("activities.coverImage.dragOrClick")}
          </p>
        </div>
      )}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/svg+xml"
        className="hidden"
        onChange={handleFileSelect}
      />
    </div>
  );
}
