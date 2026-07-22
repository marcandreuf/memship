"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TabContentSkeleton } from "@/components/ui/skeletons";
import { useCancelBooking, useSpaceBookings } from "../hooks/use-bookings";
import type { AdminBooking, BookingStatus } from "../services/bookings-api";

const statusVariant: Record<
  BookingStatus,
  "default" | "secondary" | "outline"
> = {
  booked: "default",
  waitlisted: "secondary",
  cancelled: "outline",
};

export function SpaceBookingsTab({ spaceId }: { spaceId: number }) {
  const t = useTranslations();
  const [page, setPage] = useState(1);
  const { data, isLoading } = useSpaceBookings(spaceId, { page, per_page: 20 });

  if (isLoading) return <TabContentSkeleton />;

  const items = data?.items ?? [];
  const totalPages = data?.meta.total_pages ?? 1;

  if (!items.length) {
    return (
      <p className="text-sm text-muted-foreground">
        {t("bookings.adminBookings.noBookings")}
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <div className="table-compact overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("bookings.adminBookings.member")}</TableHead>
              <TableHead>{t("bookings.adminBookings.date")}</TableHead>
              <TableHead>{t("bookings.adminBookings.time")}</TableHead>
              <TableHead>{t("bookings.adminBookings.status")}</TableHead>
              <TableHead>{t("common.actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((booking) => (
              <BookingRow key={booking.id} spaceId={spaceId} booking={booking} />
            ))}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-end gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            {t("common.previous")}
          </Button>
          <span className="text-xs text-muted-foreground">
            {page} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            {t("common.next")}
          </Button>
        </div>
      )}
    </div>
  );
}

function BookingRow({
  spaceId,
  booking,
}: {
  spaceId: number;
  booking: AdminBooking;
}) {
  const t = useTranslations();
  const cancelMutation = useCancelBooking(spaceId);
  const [confirmDialog, confirmAction] = useConfirmDialog();

  const time = `${booking.start_time.slice(0, 5)}–${booking.end_time.slice(0, 5)}`;

  return (
    <TableRow>
      <TableCell className="font-medium">{booking.member_name}</TableCell>
      <TableCell>{booking.booking_date}</TableCell>
      <TableCell>{time}</TableCell>
      <TableCell>
        <Badge variant={statusVariant[booking.status]}>
          {t(`bookings.status.${booking.status}`)}
        </Badge>
      </TableCell>
      <TableCell>
        {confirmDialog}
        {booking.status !== "cancelled" && (
          <Button
            variant="outline"
            size="sm"
            disabled={cancelMutation.isPending}
            onClick={() =>
              confirmAction({
                title: t("bookings.adminBookings.confirmCancel"),
                cancelLabel: t("common.cancel"),
                confirmLabel: t("bookings.adminBookings.cancel"),
                onConfirm: async () => {
                  try {
                    await cancelMutation.mutateAsync(booking.id);
                    toast.success(t("toast.success.saved"));
                  } catch {
                    /* global handler */
                  }
                },
              })
            }
          >
            {t("bookings.adminBookings.cancel")}
          </Button>
        )}
      </TableCell>
    </TableRow>
  );
}
