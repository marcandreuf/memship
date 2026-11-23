"use client";

import { useState, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TabContentSkeleton } from "@/components/ui/skeletons";
import { Link } from "@/lib/i18n/routing";
import { useFormatters } from "@/hooks/use-formatters";
import { useLocaleDate } from "@/hooks/use-locale-date";
import { BOOKING_STATUS_VARIANTS, RECEIPT_STATUS_VARIANTS } from "@/lib/status-variants";
import { usePermissions } from "@/features/auth/hooks/use-permissions";
import { CancelPaidSeatDialog } from "@/features/activities/components/registrations-tab";
import {
  useCancelBooking,
  useConfirmBookingWithoutPayment,
  useSpaceBookings,
} from "../hooks/use-bookings";
import type { AdminBooking, BookingStatus } from "../services/bookings-api";

const STATUS_FILTERS: BookingStatus[] = ["booked", "pending", "waitlisted", "cancelled"];

const timeRange = (b: AdminBooking) => `${b.start_time.slice(0, 5)}–${b.end_time.slice(0, 5)}`;

export function SpaceBookingsTab({ spaceId }: { spaceId: number }) {
  const t = useTranslations();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<BookingStatus | "all">("all");
  const { data, isLoading } = useSpaceBookings(spaceId, {
    page,
    per_page: 20,
    status: status === "all" ? undefined : status,
  });

  const items = data?.items ?? [];
  const totalPages = data?.meta.total_pages ?? 1;

  return (
    <div className="space-y-3">
      <Select
        value={status}
        onValueChange={(v) => {
          setStatus(v as BookingStatus | "all");
          setPage(1);
        }}
      >
        <SelectTrigger className="sm:w-48">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">{t("bookings.adminBookings.allStatuses")}</SelectItem>
          {STATUS_FILTERS.map((s) => (
            <SelectItem key={s} value={s}>
              {t(`bookings.status.${s}`)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {isLoading ? (
        <TabContentSkeleton />
      ) : !items.length ? (
        <p className="text-sm text-muted-foreground">
          {status === "all"
            ? t("bookings.adminBookings.noBookings")
            : t("bookings.adminBookings.noBookingsFiltered")}
        </p>
      ) : (
        <>
          <div className="hidden md:block table-compact overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("bookings.adminBookings.member")}</TableHead>
                  <TableHead>{t("bookings.adminBookings.date")}</TableHead>
                  <TableHead>{t("bookings.adminBookings.time")}</TableHead>
                  <TableHead>{t("bookings.adminBookings.status")}</TableHead>
                  <TableHead>{t("bookings.adminBookings.payment")}</TableHead>
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

          {/* On a phone the table's payment column and actions sat off screen
              behind a horizontal scroll; each booking is a card instead. */}
          <div className="space-y-3 md:hidden">
            {items.map((booking) => (
              <BookingCard key={booking.id} spaceId={spaceId} booking={booking} />
            ))}
          </div>
        </>
      )}

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

/**
 * What the club can do with one booking — confirm it without payment, cancel
 * it, and decide about the money when it was paid — shared by the table row
 * and the phone card so both offer exactly the same.
 */
function useBookingActions(spaceId: number, booking: AdminBooking) {
  const t = useTranslations();
  const { has } = usePermissions();
  const cancelMutation = useCancelBooking(spaceId);
  const waiveMutation = useConfirmBookingWithoutPayment(spaceId);
  const [confirmDialog, confirmAction] = useConfirmDialog();
  const [cancellingPaid, setCancellingPaid] = useState(false);
  const paid = booking.receipt_status === "paid";

  async function cancel(keepPayment = false) {
    try {
      await cancelMutation.mutateAsync({ id: booking.id, keepPayment });
      toast.success(t("toast.success.saved"));
    } catch {
      /* global handler */
    }
  }

  function handleCancel() {
    if (paid) {
      setCancellingPaid(true);
      return;
    }
    confirmAction({
      title: t("bookings.adminBookings.confirmCancel"),
      description: t("bookings.adminBookings.confirmCancelDescription"),
      cancelLabel: t("common.back"),
      confirmLabel: t("bookings.adminBookings.cancel"),
      onConfirm: () => cancel(),
    });
  }

  function handleWaive() {
    confirmAction({
      title: t("activities.registration.confirmWithoutPaymentTitle"),
      description: t("bookings.adminBookings.confirmWithoutPaymentDescription"),
      cancelLabel: t("common.back"),
      confirmLabel: t("activities.registration.confirmWithoutPayment"),
      onConfirm: async () => {
        try {
          await waiveMutation.mutateAsync(booking.id);
          toast.success(t("toast.success.updated"));
        } catch {
          /* global handler */
        }
      },
    });
  }

  const buttons = (
    <div className="flex flex-wrap items-center gap-2">
      {booking.status === "pending" && has("billing.write") && (
        <Button size="sm" variant="outline" className="h-8 text-xs" onClick={handleWaive}>
          {t("activities.registration.confirmWithoutPayment")}
        </Button>
      )}
      {booking.status !== "cancelled" && (
        <Button
          variant="outline"
          size="sm"
          className="h-8 text-xs"
          disabled={cancelMutation.isPending}
          onClick={handleCancel}
        >
          {t("bookings.adminBookings.cancel")}
        </Button>
      )}
    </div>
  );

  const dialogs = (
    <>
      {confirmDialog}
      <CancelPaidSeatDialog
        open={cancellingPaid}
        onOpenChange={setCancellingPaid}
        title={t("bookings.adminBookings.paidTitle")}
        description={t("activities.registration.keepPaymentDescription")}
        confirmLabel={t("bookings.adminBookings.cancel")}
        onConfirm={(keepPayment) => {
          setCancellingPaid(false);
          cancel(keepPayment);
        }}
      />
    </>
  );

  return { buttons, dialogs, canOpenReceipt: has("billing.read") };
}

function BookingRow({ spaceId, booking }: { spaceId: number; booking: AdminBooking }) {
  const { formatDate } = useFormatters();
  const { buttons, dialogs, canOpenReceipt } = useBookingActions(spaceId, booking);

  return (
    <TableRow>
      <TableCell className="font-medium">{booking.member_name}</TableCell>
      <TableCell>{formatDate(booking.slot_date)}</TableCell>
      <TableCell>{timeRange(booking)}</TableCell>
      <TableCell>
        <StatusBadges booking={booking} />
      </TableCell>
      <TableCell>
        <PaymentCell booking={booking} canOpenReceipt={canOpenReceipt} />
      </TableCell>
      <TableCell>
        {dialogs}
        {buttons}
      </TableCell>
    </TableRow>
  );
}

function BookingCard({ spaceId, booking }: { spaceId: number; booking: AdminBooking }) {
  const { formatDate } = useFormatters();
  const { buttons, dialogs, canOpenReceipt } = useBookingActions(spaceId, booking);

  return (
    <div className="space-y-2 rounded-lg border p-3 text-sm">
      {dialogs}
      <div>
        <p className="font-medium">{booking.member_name}</p>
        <p className="text-muted-foreground">
          {formatDate(booking.slot_date)} · {timeRange(booking)}
        </p>
      </div>
      <StatusBadges booking={booking} />
      <PaymentCell booking={booking} canOpenReceipt={canOpenReceipt} />
      {buttons}
    </div>
  );
}

function StatusBadges({ booking }: { booking: AdminBooking }) {
  const t = useTranslations();
  const badges: ReactNode[] = [
    <Badge key="status" variant={BOOKING_STATUS_VARIANTS[booking.status] || "outline"}>
      {t(`bookings.status.${booking.status}`)}
    </Badge>,
  ];
  if (booking.cancelled_cause === "payment_expired") {
    badges.push(
      <span key="expired" className="text-xs text-muted-foreground">
        {t("bookings.adminBookings.expired")}
      </span>
    );
  }
  if (booking.late_payment_at) {
    badges.push(
      <Badge key="late" variant="destructive">
        {t("activities.registration.latePayment")}
      </Badge>
    );
  }
  if (booking.refund_status === "due") {
    badges.push(
      <Badge key="refund" variant="outline">
        {t("activities.registration.refundDue")}
      </Badge>
    );
  }
  if (booking.refund_status === "returned") {
    badges.push(
      <Badge key="returned" variant="secondary">
        {t("activities.registration.refundReturned")}
      </Badge>
    );
  }
  return <div className="flex flex-wrap items-center gap-1">{badges}</div>;
}

/**
 * The receipt's state, linked to the receipt itself, which is where the club
 * marks a transfer or cash payment received. While pending, the deadline.
 */
function PaymentCell({
  booking,
  canOpenReceipt,
}: {
  booking: AdminBooking;
  canOpenReceipt: boolean;
}) {
  const t = useTranslations();
  const { shortDateTime } = useLocaleDate();
  const receiptStatus = booking.receipt_status;
  if (!receiptStatus || booking.receipt_id == null) {
    return <span className="text-sm text-muted-foreground">—</span>;
  }
  // A booked booking whose receipt was voided was confirmed without payment:
  // "Cancelled" read as if the booking itself had been.
  const waived = booking.status === "booked" && receiptStatus === "cancelled";
  const label = waived
    ? t("bookings.adminBookings.waived")
    : t(`receipts.status${receiptStatus.charAt(0).toUpperCase() + receiptStatus.slice(1)}`);
  const badge = (
    <Badge variant={waived ? "secondary" : RECEIPT_STATUS_VARIANTS[receiptStatus] || "outline"}>
      {label}
    </Badge>
  );
  return (
    <div className="space-y-0.5">
      {canOpenReceipt ? (
        <Link
          href={`/receipts/${booking.receipt_id}`}
          aria-label={t("activities.registration.openReceipt")}
        >
          {badge}
        </Link>
      ) : (
        badge
      )}
      {booking.status === "pending" && booking.payment_due_at && (
        <p className="text-xs text-muted-foreground">
          {t("activities.registration.payBy", { date: shortDateTime(booking.payment_due_at) })}
        </p>
      )}
    </div>
  );
}
