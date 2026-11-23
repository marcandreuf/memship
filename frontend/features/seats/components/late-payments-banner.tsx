"use client";

import { useTranslations } from "next-intl";
import { AlertTriangle } from "lucide-react";
import { Link } from "@/lib/i18n/routing";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { usePermissions } from "@/features/auth/hooks/use-permissions";
import { useAcknowledgeLatePayment, useUnseenLatePayments } from "../hooks/use-seats";
import { seatOwnerHref } from "../services/seats-api";

/**
 * Payments the gateway collected for seats already released. Urgent: only the
 * club can return the money, so each one stays here until someone has looked.
 */
export function LatePaymentsBanner() {
  const t = useTranslations();
  const { has } = usePermissions();
  const { data, isError } = useUnseenLatePayments();
  const acknowledge = useAcknowledgeLatePayment();
  const items = data?.items ?? [];
  // A failed check must not look like "nothing to report": these are payments
  // only the club can return.
  if (isError) {
    return (
      <div role="alert" className="flex items-center gap-2 rounded-md border border-destructive/50 bg-destructive/5 p-3 text-sm">
        <AlertTriangle className="h-4 w-4 shrink-0 text-destructive" aria-hidden />
        {t("dashboard.latePayments.loadError")}
      </div>
    );
  }
  if (!items.length) return null;

  return (
    <div
      role="alert"
      className="space-y-2 rounded-md border border-destructive/50 bg-destructive/5 p-3"
    >
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden />
        <div>
          <p className="font-medium">{t("dashboard.latePayments.title")}</p>
          <p className="text-sm text-muted-foreground">{t("dashboard.latePayments.description")}</p>
        </div>
      </div>
      <ul className="space-y-1">
        {items.map((item) => (
          <li key={`${item.kind}-${item.seat_id}`} className="flex flex-wrap items-center gap-2 text-sm">
            <Link href={seatOwnerHref(item)} className="font-medium hover:underline">
              {item.member_name ?? "—"} · {item.owner_name}
            </Link>
            <Badge variant={item.refund_status === "due" ? "destructive" : "secondary"}>
              {item.refund_status === "due"
                ? t("dashboard.latePayments.refundDue")
                : t("dashboard.latePayments.confirmed")}
            </Badge>
            {has("billing.write") && (
              <Button
                size="sm"
                variant="ghost"
                className="h-7"
                onClick={() => acknowledge.mutate({ kind: item.kind, seatId: item.seat_id })}
              >
                {t("dashboard.latePayments.seen")}
              </Button>
            )}
          </li>
        ))}
      </ul>
      <Link href="/refunds" className="text-sm underline">
        {t("dashboard.latePayments.viewRefunds")}
      </Link>
    </div>
  );
}
