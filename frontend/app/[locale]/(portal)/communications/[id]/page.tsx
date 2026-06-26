"use client";

import { use } from "react";
import { useTranslations } from "next-intl";
import { DetailHeader } from "@/components/entity/detail-header";
import { DetailSkeleton } from "@/components/ui/skeletons";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { AnnouncementForm } from "@/features/communications/components/announcement-form";
import { useAnnouncement } from "@/features/communications/hooks/use-announcements";

export default function AnnouncementDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const t = useTranslations();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin" || user?.role === "super_admin";
  const { data: announcement, isLoading } = useAnnouncement(Number(id));

  if (!isAdmin) {
    return (
      <div className="py-8 text-center text-muted-foreground">
        {t("settings.noAccess")}
      </div>
    );
  }

  if (isLoading) return <DetailSkeleton />;

  if (!announcement) {
    return (
      <div className="py-8 text-center text-muted-foreground">
        {t("common.notFound")}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <DetailHeader
        breadcrumbs={[
          { label: t("communications.title"), href: "/communications" },
          { label: announcement.subject },
        ]}
        title={announcement.subject}
      />
      <AnnouncementForm announcement={announcement} />
    </div>
  );
}
