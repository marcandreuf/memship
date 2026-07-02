"use client";

import { useTranslations } from "next-intl";
import {
  Card, CardContent, CardHeader, CardTitle,
} from "@/components/ui/card";
import { DetailSection } from "@/components/entity/detail-section";
import { EntityTabs } from "@/components/entity/entity-tabs";
import { Markdown } from "@/lib/markdown";
import { useFormatters } from "@/hooks/use-formatters";
import { useGroups } from "@/features/groups/hooks/use-groups";
import { useMembershipTypes } from "@/features/members/hooks/use-members";
import { useAnnouncementStats } from "../hooks/use-announcements";
import { RecipientsTab } from "./recipients-tab";
import type { AnnouncementData } from "../services/announcements-api";

export function SentAnnouncementView({
  announcement,
}: {
  announcement: AnnouncementData;
}) {
  const t = useTranslations();
  const { formatDateTime } = useFormatters();
  const { data: stats } = useAnnouncementStats(announcement.id);
  const { data: groups } = useGroups();
  const { data: membershipTypes } = useMembershipTypes();

  function targetLabel() {
    if (announcement.target_type === "all") return t("communications.target.all");
    if (announcement.target_type === "group") {
      const g = (groups ?? []).find((x) => x.id === announcement.target_id);
      return `${t("communications.target.group")}: ${g?.name ?? "—"}`;
    }
    const mt = (membershipTypes ?? []).find((x) => x.id === announcement.target_id);
    return `${t("communications.target.membership_type")}: ${mt?.name ?? "—"}`;
  }

  const recipientCount = stats?.recipient_count ?? announcement.recipient_count ?? 0;
  const seenCount = stats?.seen_count ?? 0;

  return (
    <div className="space-y-4 max-w-4xl">
      {/* Content header — subject + rendered body + summary line */}
      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-lg">{announcement.subject}</CardTitle>
          <p className="text-sm text-muted-foreground">
            {t("communications.view.summary", {
              date: announcement.sent_at ? formatDateTime(announcement.sent_at) : "—",
              recipients: recipientCount,
              seen: seenCount,
            })}
          </p>
        </CardHeader>
        <CardContent className="px-4 pb-4 pt-0">
          <Markdown
            content={announcement.body}
            className="text-sm prose-sm [&_p]:my-1 [&_ul]:my-1 [&_ul]:list-disc [&_ul]:pl-5 [&_a]:text-primary [&_a]:underline"
          />
        </CardContent>
      </Card>

      <EntityTabs
        lazy
        tabs={[
          {
            id: "details",
            label: t("communications.view.detailsTab"),
            content: (
              <Card>
                <CardContent className="p-4">
                  <DetailSection
                    columns={2}
                    fields={[
                      { label: t("communications.view.sentAt"), value: announcement.sent_at ? formatDateTime(announcement.sent_at) : "—" },
                      { label: t("communications.view.sentBy"), value: stats?.sent_by ?? "—" },
                      { label: t("communications.view.target"), value: targetLabel() },
                      { label: t("communications.view.recipientCount"), value: recipientCount },
                      { label: t("communications.view.emailedCount"), value: stats?.emailed_count ?? "—" },
                      { label: t("communications.view.seenCount"), value: seenCount },
                      { label: t("communications.view.createdAt"), value: announcement.created_at ? formatDateTime(announcement.created_at) : "—" },
                    ]}
                  />
                </CardContent>
              </Card>
            ),
          },
          {
            id: "recipients",
            label: t("communications.view.recipientsTab"),
            badge: recipientCount,
            content: <RecipientsTab announcementId={announcement.id} />,
          },
        ]}
      />
    </div>
  );
}
