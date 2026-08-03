"use client";

import { useTranslations } from "next-intl";
import { DetailHeader } from "@/components/entity/detail-header";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { usePermissions } from "@/features/auth/hooks/use-permissions";
import { AnnouncementForm } from "@/features/communications/components/announcement-form";

export default function NewAnnouncementPage() {
  const t = useTranslations();
  const { user } = useAuth();
  const { has } = usePermissions();
  const isAdmin = has("communications.write");

  if (!isAdmin) {
    return (
      <div className="py-8 text-center text-muted-foreground">
        {t("settings.noAccess")}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <DetailHeader
        breadcrumbs={[
          { label: t("communications.title"), href: "/communications" },
          { label: t("communications.new") },
        ]}
        title={t("communications.new")}
      />
      <AnnouncementForm />
    </div>
  );
}
