"use client";

import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { TabContentSkeleton } from "@/components/ui/skeletons";
import { useFormatters } from "@/hooks/use-formatters";
import { useLocaleDate } from "@/hooks/use-locale-date";
import { useRouter } from "@/lib/i18n/routing";
import { useCancelBooking, useMyBookings } from "../hooks/use-bookings";
import type { MyBooking } from "../services/bookings-api";

const hhmm = (t: string) => t.slice(0, 5);

// "YYYY-MM-DD" → weekday 0=Mon … 6=Sun, parsed as a local date.
function isoWeekday(dateStr: string): number {
  const [y, m, d] = dateStr.split("-").map(Number);
  return (new Date(y, m - 1, d).getDay() + 6) % 7;
}

function StatusBadge({ booking }: { booking: MyBooking }) {
  const t = useTranslations();
  const label = `${t(`bookings.status.${booking.status}`)}${
    booking.status === "waitlisted" && booking.waitlist_position
      ? ` #${booking.waitlist_position}`
      : ""
  }`;
  if (booking.status === "booked") {
    return <Badge className="bg-emerald-600 hover:bg-emerald-600">{label}</Badge>;
  }
  if (booking.status === "pending") {
    return <Badge variant="warning">{label}</Badge>;
  }
  return (
    <Badge className="bg-amber-100 text-amber-900 hover:bg-amber-100 dark:bg-amber-900/40 dark:text-amber-200">
      {label}
    </Badge>
  );
}

export function MyBookingsList({ scope }: { scope: "upcoming" | "past" }) {
  const t = useTranslations();
  const router = useRouter();
  const { formatDate } = useFormatters();
  const { shortDateTime } = useLocaleDate();
  const { data = [], isLoading } = useMyBookings(scope);
  const cancel = useCancelBooking();
  const [confirmDialog, confirmAction] = useConfirmDialog();

  if (isLoading) return <TabContentSkeleton />;
  if (!data.length)
    return (
      <p className="text-sm text-muted-foreground">{t("bookings.my.empty")}</p>
    );

  return (
    <div className="space-y-2">
      {confirmDialog}
      {data.map((b) => (
        <div key={b.id} className="space-y-2 rounded-lg border p-3 text-sm">
          <div className="flex items-center justify-between gap-2">
            <div>
              <div className="font-medium">{b.space_name}</div>
              <div className="text-muted-foreground">
                {t(`bookings.weekdays.${isoWeekday(b.slot_date)}`)}{" "}
                {formatDate(b.slot_date)} · {hhmm(b.start_time)}–{hhmm(b.end_time)}{" "}
                · {b.booked_count}/{b.capacity}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge booking={b} />
              {scope === "upcoming" && !b.can_cancel && (
                // Past the deadline the server refuses a member's own
                // cancellation, so the button would only produce an error.
                <span className="text-xs text-muted-foreground">
                  {t("bookings.my.cancelClosed")}
                </span>
              )}
              {scope === "upcoming" && b.can_cancel && (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={cancel.isPending}
                  onClick={() =>
                    confirmAction({
                      title: t("bookings.my.confirmCancel"),
                      description: t(
                        b.cancel_refundable
                          ? "bookings.my.confirmCancelDescription"
                          : "bookings.my.confirmCancelLateDescription"
                      ),
                      cancelLabel: t("bookings.my.keep"),
                      confirmLabel: t("bookings.my.cancel"),
                      onConfirm: async () => {
                        try {
                          await cancel.mutateAsync({ id: b.id });
                          toast.success(t("toast.success.saved"));
                        } catch {
                          /* global handler shows the error toast */
                        }
                      },
                    })
                  }
                >
                  {t("bookings.my.cancel")}
                </Button>
              )}
            </div>
          </div>
          {b.status === "pending" && (
            /* Held until paid (#603): until when, and the way to pay. */
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-amber-300 bg-amber-50 p-2 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
              <span>
                {b.payment_due_at
                  ? t("bookings.my.payBy", { date: shortDateTime(b.payment_due_at) })
                  : t("bookings.my.pendingNotice")}
              </span>
              <Button size="sm" onClick={() => router.push("/my-receipts")}>
                {t("receipts.payNow")}
              </Button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
