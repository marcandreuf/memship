"use client";

import { use } from "react";
import { useTranslations } from "next-intl";
import { DetailHeader } from "@/components/entity/detail-header";
import { DetailSkeleton } from "@/components/ui/skeletons";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { usePermissions } from "@/features/auth/hooks/use-permissions";
import { AnnouncementForm } from "@/features/communications/components/announcement-form";
import { SentAnnouncementView } from "@/features/communications/components/sent-announcement-view";
import { useAnnouncement } from "@/features/communications/hooks/use-announcements";

export default function AnnouncementDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const t = useTranslations();
  const { user } = useAuth();
  const { has } = usePermissions();
  const isAdmin = has("communications.read");
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
      {announcement.status === "sent" ? (
        <SentAnnouncementView announcement={announcement} />
      ) : (
        <AnnouncementForm announcement={announcement} />
      )}
    </div>
  );
}
