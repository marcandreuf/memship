"use client";

import { useTranslations } from "next-intl";
import { AlertTriangle } from "lucide-react";
import { Link } from "@/lib/i18n/routing";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { usePermissions } from "@/features/auth/hooks/use-permissions";
import { useAcknowledgeLatePayment, useUnseenLatePayments } from "../hooks/use-registrations";

/**
 * Payments the gateway collected for seats already released. Urgent: only the
 * club can return the money, so each one stays here until someone has looked.
 */
export function LatePaymentsBanner() {
  const t = useTranslations();
  const { has } = usePermissions();
  const { data } = useUnseenLatePayments();
  const acknowledge = useAcknowledgeLatePayment();
  const items = data?.items ?? [];
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
          <li key={item.registration_id} className="flex flex-wrap items-center gap-2 text-sm">
            <Link href={`/activities/${item.activity_id}`} className="font-medium hover:underline">
              {item.member_name ?? "—"} · {item.activity_name}
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
                onClick={() => acknowledge.mutate(item.registration_id)}
              >
                {t("dashboard.latePayments.seen")}
              </Button>
            )}
          </li>
        ))}
      </ul>
      <Link href="/activities/refunds" className="text-sm underline">
        {t("dashboard.latePayments.viewRefunds")}
      </Link>
    </div>
  );
}
