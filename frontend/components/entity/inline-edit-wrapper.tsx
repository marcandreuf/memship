"use client";

import { type ReactNode } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface InlineEditWrapperProps {
  title?: string;
  isEditing: boolean;
  onEdit: () => void;
  onCancel: () => void;
  readContent: ReactNode;
  editContent: ReactNode;
  canEdit?: boolean;
}

export function InlineEditWrapper({
  title,
  isEditing,
  onEdit,
  onCancel,
  readContent,
  editContent,
  canEdit = true,
}: InlineEditWrapperProps) {
  const t = useTranslations();

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between py-3 px-4">
        {title && <CardTitle className="text-base">{title}</CardTitle>}
        {canEdit && !isEditing && (
          <Button variant="outline" size="xs" onClick={onEdit}>
            {t("common.edit")}
          </Button>
        )}
      </CardHeader>
      <CardContent className="px-4 pb-4 pt-0">{isEditing ? editContent : readContent}</CardContent>
    </Card>
  );
}
