"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { TableSkeleton } from "@/components/ui/skeletons";
import { Pagination } from "@/components/entity/pagination";
import { Link } from "@/lib/i18n/routing";
import { formatDateTime } from "@/lib/formatters";
import { useWebhookEvents } from "../hooks/use-payment-providers";
import type { WebhookEvent, WebhookEventStatus } from "../services/payment-providers-api";

const NEEDS_A_LOOK: WebhookEventStatus[] = ["failed", "ignored"];
const EVERYTHING: WebhookEventStatus[] = ["failed", "ignored", "received", "processed"];

const STATUS_VARIANT: Record<WebhookEventStatus, "destructive" | "secondary" | "outline"> = {
  failed: "destructive",
  ignored: "secondary",
  received: "outline",
  processed: "outline",
};

/**
 * Gateway notifications memship could not apply or chose to ignore (#435).
 *
 * An `ignored` one for a receipt already paid is how a second charge shows up,
 * so it is listed beside `failed` by default rather than hidden with the
 * routine `processed` ones.
 */
export function WebhookEventsCard() {
  const t = useTranslations();
  const [showAll, setShowAll] = useState(false);
  const [page, setPage] = useState(1);
  const { data, isLoading } = useWebhookEvents(showAll ? EVERYTHING : NEEDS_A_LOOK, page);
  const events = data?.items ?? [];

  function toggleShowAll(checked: boolean) {
    setShowAll(checked);
    setPage(1);
  }

  return (
    <Card data-testid="webhook-events">
      <CardHeader className="py-3 px-4 flex flex-col items-start gap-2 @md:flex-row @md:items-center @md:justify-between">
        <div>
          <CardTitle className="text-base">{t("settings.providers.webhookEvents.title")}</CardTitle>
          <CardDescription className="text-xs">
            {t("settings.providers.webhookEvents.description")}
          </CardDescription>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Switch id="webhook-events-all" checked={showAll} onCheckedChange={toggleShowAll} />
          <Label htmlFor="webhook-events-all" className="text-xs">
            {t("settings.providers.webhookEvents.showAll")}
          </Label>
        </div>
      </CardHeader>
      <CardContent className="px-4 pb-3 pt-0 space-y-3">
        {isLoading ? (
          <TableSkeleton rows={3} columns={6} />
        ) : events.length === 0 ? (
          <div className="py-8 text-center text-muted-foreground text-sm">
            {t("settings.providers.webhookEvents.empty")}
          </div>
        ) : (
          <>
            <div className="hidden md:block rounded-md border">
              <Table className="table-compact">
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("settings.providers.webhookEvents.date")}</TableHead>
                    <TableHead>{t("settings.providers.webhookEvents.provider")}</TableHead>
                    <TableHead>{t("settings.providers.webhookEvents.eventType")}</TableHead>
                    <TableHead>{t("settings.providers.webhookEvents.status")}</TableHead>
                    <TableHead>{t("settings.providers.webhookEvents.receipt")}</TableHead>
                    <TableHead>{t("settings.providers.webhookEvents.reason")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {events.map((event) => (
                    <TableRow key={event.id}>
                      <TableCell className="whitespace-nowrap">{formatDateTime(event.created_at)}</TableCell>
                      <TableCell>{event.provider_type}</TableCell>
                      <TableCell className="font-mono text-xs">{event.event_type}</TableCell>
                      <TableCell><StatusBadge event={event} /></TableCell>
                      <TableCell><ReceiptLink event={event} /></TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {event.error_message ?? "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <div className="space-y-2 md:hidden">
              {events.map((event) => (
                <div key={event.id} className="rounded-lg border p-3 space-y-1 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium">{event.provider_type}</span>
                    <StatusBadge event={event} />
                  </div>
                  <p className="text-xs text-muted-foreground">{formatDateTime(event.created_at)}</p>
                  <p className="font-mono text-xs break-all">{event.event_type}</p>
                  {event.receipt_id && <ReceiptLink event={event} />}
                  {event.error_message && (
                    <p className="text-xs text-muted-foreground">{event.error_message}</p>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
        {data && (
          <Pagination
            page={data.meta.page}
            totalPages={data.meta.total_pages}
            total={data.meta.total}
            perPage={data.meta.per_page}
            onPageChange={setPage}
          />
        )}
      </CardContent>
    </Card>
  );
}

function StatusBadge({ event }: { event: WebhookEvent }) {
  const t = useTranslations();
  return (
    <Badge variant={STATUS_VARIANT[event.status]}>
      {t(`settings.providers.webhookEvents.statuses.${event.status}`)}
    </Badge>
  );
}

function ReceiptLink({ event }: { event: WebhookEvent }) {
  if (!event.receipt_id) return <>—</>;
  return (
    <Link href={`/receipts/${event.receipt_id}`} className="text-primary hover:underline">
      {event.receipt_number ?? `#${event.receipt_id}`}
    </Link>
  );
}
