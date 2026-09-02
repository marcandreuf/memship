"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter, Link } from "@/lib/i18n/routing";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Pagination } from "@/components/entity/pagination";
import { PageInfo } from "@/components/page-info";
import { TableSkeleton } from "@/components/ui/skeletons";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { usePermissions } from "@/features/auth/hooks/use-permissions";
import { useAnnouncements } from "@/features/communications/hooks/use-announcements";
import type { AnnouncementData } from "@/features/communications/services/announcements-api";
import { useFormatters } from "@/hooks/use-formatters";

export default function CommunicationsPage() {
  const t = useTranslations();
  const router = useRouter();
  const { user } = useAuth();
  const { has } = usePermissions();
  const isAdmin = has("communications.read");
  const [page, setPage] = useState(1);
  const { data, isLoading } = useAnnouncements({ page, per_page: 20 });
  const { formatDate } = useFormatters();

  if (!isAdmin) {
    return (
      <div className="py-8 text-center text-muted-foreground">
        {t("settings.noAccess")}
      </div>
    );
  }

  const items = data?.items ?? [];
  const meta = data?.meta ?? { page: 1, per_page: 20, total: 0, total_pages: 1 };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">{t("communications.title")}</h1>
            <PageInfo text={t("communications.info")} />
          </div>
          <p className="text-sm text-muted-foreground">
            {t("communications.subtitle")}
          </p>
        </div>
        <Button asChild>
          <Link href="/communications/new">{t("communications.new")}</Link>
        </Button>
      </div>

      {isLoading ? (
        <TableSkeleton />
      ) : items.length === 0 ? (
        <div className="py-8 text-center text-muted-foreground">
          {t("communications.empty")}
        </div>
      ) : (
        <>
        <div className="hidden md:block rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("communications.columns.subject")}</TableHead>
              <TableHead>{t("communications.columns.target")}</TableHead>
              <TableHead>{t("communications.columns.status")}</TableHead>
              <TableHead className="text-right">
                {t("communications.columns.recipients")}
              </TableHead>
              <TableHead>{t("communications.columns.sentAt")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((a: AnnouncementData) => (
              <TableRow
                key={a.id}
                className="cursor-pointer hover:bg-muted/50"
                onClick={() => router.push(`/communications/${a.id}`)}
              >
                <TableCell className="font-medium">{a.subject}</TableCell>
                <TableCell>{t(`communications.target.${a.target_type}`)}</TableCell>
                <TableCell>
                  <Badge variant={a.status === "sent" ? "default" : "secondary"}>
                    {t(`communications.status.${a.status}`)}
                  </Badge>
                </TableCell>
                <TableCell className="text-right font-mono">
                  {a.recipient_count ?? "—"}
                </TableCell>
                <TableCell className="text-sm">
                  {a.sent_at ? formatDate(a.sent_at) : "—"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        </div>

        <div className="space-y-3 md:hidden">
          {items.map((a: AnnouncementData) => (
            <Link
              key={a.id}
              href={`/communications/${a.id}`}
              className="block rounded-lg border p-4 hover:bg-accent transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate font-medium">{a.subject}</p>
                  <p className="text-sm text-muted-foreground">
                    {t(`communications.target.${a.target_type}`)}
                  </p>
                </div>
                <Badge variant={a.status === "sent" ? "default" : "secondary"}>
                  {t(`communications.status.${a.status}`)}
                </Badge>
              </div>
              <div className="mt-1 flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                  {a.sent_at ? formatDate(a.sent_at) : "—"}
                </span>
                <span className="font-mono text-sm">{a.recipient_count ?? "—"}</span>
              </div>
            </Link>
          ))}
        </div>
        </>
      )}

      <Pagination
        page={meta.page}
        totalPages={meta.total_pages}
        total={meta.total}
        perPage={meta.per_page}
        onPageChange={(p) => setPage(p)}
      />
    </div>
  );
}
