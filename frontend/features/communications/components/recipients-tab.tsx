"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { TabContentSkeleton } from "@/components/ui/skeletons";
import { Pagination } from "@/components/entity/pagination";
import { useFormatters } from "@/hooks/use-formatters";
import { useAnnouncementRecipients } from "../hooks/use-announcements";

export function RecipientsTab({ announcementId }: { announcementId: number }) {
  const t = useTranslations();
  const { formatDateTime } = useFormatters();
  const [page, setPage] = useState(1);
  const { data, isLoading } = useAnnouncementRecipients(announcementId, page);

  if (isLoading) return <TabContentSkeleton />;

  const items = data?.items ?? [];
  const meta = data?.meta;

  if (!items.length) {
    return (
      <p className="text-sm text-muted-foreground py-4">
        {t("communications.view.noRecipients")}
      </p>
    );
  }

  return (
    <div className="space-y-4 table-compact">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t("communications.view.recipientName")}</TableHead>
            <TableHead>{t("communications.view.recipientEmail")}</TableHead>
            <TableHead>{t("communications.view.channel")}</TableHead>
            <TableHead>{t("communications.view.seen")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((r) => (
            <TableRow key={r.member_id}>
              <TableCell className="font-medium">{r.name}</TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {r.email || "—"}
              </TableCell>
              <TableCell>
                <div className="flex gap-1">
                  {r.emailed && (
                    <Badge variant="outline">
                      {t("communications.view.channelEmail")}
                    </Badge>
                  )}
                  {r.in_app && (
                    <Badge variant="outline">
                      {t("communications.view.channelInApp")}
                    </Badge>
                  )}
                </div>
              </TableCell>
              <TableCell>
                {r.seen_at ? (
                  <Badge className="bg-emerald-600 hover:bg-emerald-600">
                    {t("communications.view.seenAt", {
                      date: formatDateTime(r.seen_at),
                    })}
                  </Badge>
                ) : r.in_app ? (
                  <Badge variant="secondary">
                    {t("communications.view.notSeen")}
                  </Badge>
                ) : (
                  <span className="text-sm text-muted-foreground">—</span>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {meta && (
        <Pagination
          page={meta.page}
          totalPages={meta.total_pages}
          total={meta.total}
          perPage={meta.per_page}
          onPageChange={setPage}
        />
      )}
    </div>
  );
}
