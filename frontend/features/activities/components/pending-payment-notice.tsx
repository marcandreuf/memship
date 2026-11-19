"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "@/lib/i18n/routing";
import { Button } from "@/components/ui/button";
import { useLocaleDate } from "@/hooks/use-locale-date";
import type { RegistrationData } from "../services/registrations-api";

/**
 * What a member with a seat held until paid needs: that it is held, until when,
 * and the way to pay. Navigates rather than links, so it can sit inside a card
 * that is itself a link.
 */
export function PendingPaymentNotice({ registration }: { registration: RegistrationData }) {
  const t = useTranslations();
  const router = useRouter();
  const { shortDateTime } = useLocaleDate();

  if (registration.status !== "pending") return null;

  return (
    <div className="space-y-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
      <p>{t("activities.registration.pendingNotice")}</p>
      {registration.payment_due_at && (
        <p className="font-medium">
          {t("activities.registration.payBy", { date: shortDateTime(registration.payment_due_at) })}
        </p>
      )}
      <Button
        size="sm"
        onClick={(e) => {
          e.preventDefault();
          router.push("/my-receipts");
        }}
      >
        {t("receipts.payNow")}
      </Button>
    </div>
  );
}
