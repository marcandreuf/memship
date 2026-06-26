"use client";

import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DetailSkeleton } from "@/components/ui/skeletons";
import { Markdown } from "@/lib/markdown";
import { useFormatters } from "@/hooks/use-formatters";
import {
  useMyAnnouncements,
  useNotifications,
} from "@/features/communications/hooks/use-notifications";

export default function AnnouncementsPage() {
  const t = useTranslations();
  const { formatDate } = useFormatters();
  const { data: announcements, isLoading } = useMyAnnouncements();
  const { data: notifications } = useNotifications();

  // Announcement ids the member hasn't read yet (unread in-app notifications).
  const unreadIds = new Set(
    (notifications ?? [])
      .filter((n) => n.source_type === "announcement" && !n.read_at)
      .map((n) => n.source_id)
  );

  if (isLoading) return <DetailSkeleton />;

  const items = announcements ?? [];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">{t("communications.list.title")}</h1>
        <p className="text-sm text-muted-foreground">
          {t("communications.list.subtitle")}
        </p>
      </div>

      {items.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          {t("communications.list.empty")}
        </p>
      ) : (
        <div className="space-y-3">
          {items.map((a) => (
            <Card key={a.id} className={unreadIds.has(a.id) ? "border-primary/50" : ""}>
              <CardHeader className="py-3 px-4">
                <div className="flex items-center justify-between gap-2">
                  <CardTitle className="text-base">{a.subject}</CardTitle>
                  {unreadIds.has(a.id) && (
                    <Badge className="shrink-0">{t("communications.list.new")}</Badge>
                  )}
                </div>
                {a.sent_at && (
                  <p className="text-xs text-muted-foreground">{formatDate(a.sent_at)}</p>
                )}
              </CardHeader>
              <CardContent className="px-4 pb-4 pt-0">
                <Markdown
                  content={a.body}
                  className="text-sm [&_p]:my-1 [&_ul]:my-1 [&_ul]:list-disc [&_ul]:pl-5 [&_a]:text-primary [&_a]:underline"
                />
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
