"use client";

import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { TabContentSkeleton } from "@/components/ui/skeletons";
import { useCancelBooking, useMyBookings } from "../hooks/use-bookings";

const hhmm = (t: string) => t.slice(0, 5);

export function MyBookingsList({ scope }: { scope: "upcoming" | "past" }) {
  const t = useTranslations();
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
        <div
          key={b.id}
          className="flex items-center justify-between gap-2 rounded-lg border p-3 text-sm"
        >
          <div>
            <div className="font-medium">{b.space_name}</div>
            <div className="text-muted-foreground">
              {t(`bookings.weekdays.${b.weekday}`)} {b.booking_date} ·{" "}
              {hhmm(b.start_time)}–{hhmm(b.end_time)}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={b.status === "booked" ? "default" : "secondary"}>
              {t(`bookings.status.${b.status}`)}
              {b.status === "waitlisted" && b.waitlist_position
                ? ` #${b.waitlist_position}`
                : ""}
            </Badge>
            {scope === "upcoming" && (
              <Button
                variant="outline"
                size="sm"
                disabled={cancel.isPending}
                onClick={() =>
                  confirmAction({
                    title: t("bookings.my.confirmCancel"),
                    cancelLabel: t("bookings.my.keep"),
                    confirmLabel: t("bookings.my.cancel"),
                    onConfirm: async () => {
                      try {
                        await cancel.mutateAsync(b.id);
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
      ))}
    </div>
  );
}
