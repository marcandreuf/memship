"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import { toast } from "sonner";
import { Link } from "@/lib/i18n/routing";
import { Pagination } from "@/components/entity/pagination";
import { ExportButton } from "@/components/entity/export-button";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  useActivityRegistrations,
  useChangeRegistrationStatus,
  useConfirmWithoutPayment,
} from "../hooks/use-registrations";
import { TabContentSkeleton } from "@/components/ui/skeletons";
import type { RegistrationData } from "../services/registrations-api";
import type { PaymentFlow } from "../services/activities-api";
import { useLocaleDate } from "@/hooks/use-locale-date";
import { usePermissions } from "@/features/auth/hooks/use-permissions";
import { RECEIPT_STATUS_VARIANTS, REGISTRATION_STATUS_VARIANTS } from "@/lib/status-variants";

interface RegistrationsTabProps {
  activityId: number;
  paymentFlow: PaymentFlow;
}

export function RegistrationsTab({ activityId, paymentFlow }: RegistrationsTabProps) {
  const t = useTranslations();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const { data, isLoading } = useActivityRegistrations({
    activityId,
    page,
    per_page: 20,
    status: statusFilter || undefined,
  });

  if (isLoading) {
    return <TabContentSkeleton />;
  }

  return (
    <div className="space-y-3 table-compact">
      <div className="flex items-center justify-between gap-3">
        <Select
          value={statusFilter}
          onValueChange={(v) => {
            setStatusFilter(v === "all" ? "" : v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-48">
            <SelectValue placeholder={t("common.filter")} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("activities.allStatuses")}</SelectItem>
            <SelectItem value="confirmed">{t("activities.registration.status.confirmed")}</SelectItem>
            <SelectItem value="pending">{t("activities.registration.status.pending")}</SelectItem>
            <SelectItem value="waitlist">{t("activities.registration.status.waitlist")}</SelectItem>
            <SelectItem value="cancelled">{t("activities.registration.status.cancelled")}</SelectItem>
          </SelectContent>
        </Select>
        <ExportButton
          path={`/api/activities/${activityId}/registrations/export.csv`}
          params={{ status: statusFilter || undefined }}
        />
      </div>

      {!data?.items.length ? (
        <p className="py-4 text-sm text-muted-foreground">{t("activities.registration.noRegistrations")}</p>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("activities.registration.member")}</TableHead>
                <TableHead>{t("common.status")}</TableHead>
                <TableHead>{t("activities.registration.payment")}</TableHead>
                <TableHead>{t("activities.registration.date")}</TableHead>
                <TableHead>{t("common.actions")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((reg) => (
                <RegistrationRow key={reg.id} registration={reg} paymentFlow={paymentFlow} />
              ))}
            </TableBody>
          </Table>

          <Pagination
            page={page}
            totalPages={data.meta.total_pages}
            total={data.meta.total}
            perPage={data.meta.per_page}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}

function RegistrationRow({
  registration,
  paymentFlow,
}: {
  registration: RegistrationData;
  paymentFlow: PaymentFlow;
}) {
  const t = useTranslations();
  const { shortDateTime: formatDate } = useLocaleDate();
  const { has } = usePermissions();
  const changeMutation = useChangeRegistrationStatus();
  const waiveMutation = useConfirmWithoutPayment();
  const [confirmDialog, confirm] = useConfirmDialog();
  const [cancellingPaid, setCancellingPaid] = useState(false);
  const memberName = registration.member
    ? `${registration.member.first_name} ${registration.member.last_name}`
    : `Party #${registration.party_id}`;

  const status = registration.status;
  const paid = registration.receipt_status === "paid";
  // Read from the seat itself, not only its amount: a pending seat owes payment
  // by definition, and so does one whose receipt is still open (#591).
  const owesPayment =
    paymentFlow === "pay_to_confirm" &&
    (status === "pending" ||
      (registration.total_amount ?? 0) > 0 ||
      (registration.receipt_status != null && registration.receipt_status !== "cancelled"));
  // A seat that needs payment is confirmed by paying or by waiving it, never by
  // a status flip; and only such a seat can be put back to pending.
  const targets = [
    ...(status !== "confirmed" && (!owesPayment || paid) ? ["confirmed"] : []),
    ...(status !== "pending" && owesPayment && !paid ? ["pending"] : []),
    // A paid seat is not sent to wait for a place it already paid for.
    ...(status !== "waitlist" && !paid ? ["waitlist"] : []),
    "cancelled",
  ];

  async function changeStatus(newStatus: string, keepPayment?: boolean) {
    try {
      await changeMutation.mutateAsync({
        id: registration.id,
        status: newStatus,
        keep_payment: keepPayment,
      });
      toast.success(t("toast.success.updated"));
    } catch { /* global handler shows error toast */ }
  }

  function handleStatusChange(newStatus: string) {
    if (newStatus === "cancelled" && paid) {
      setCancellingPaid(true);
      return;
    }
    changeStatus(newStatus);
  }

  function handleWaive() {
    confirm({
      title: t("activities.registration.confirmWithoutPaymentTitle"),
      description: t("activities.registration.confirmWithoutPaymentDescription"),
      confirmLabel: t("activities.registration.confirmWithoutPayment"),
      onConfirm: async () => {
        try {
          await waiveMutation.mutateAsync(registration.id);
          toast.success(t("toast.success.updated"));
        } catch { /* global handler shows error toast */ }
      },
    });
  }

  return (
    <TableRow>
      <TableCell>
        <div>
          <span className="font-medium">{memberName}</span>
          {registration.member?.member_number && (
            <span className="ml-2 text-xs text-muted-foreground font-mono">
              {registration.member.member_number}
            </span>
          )}
        </div>
      </TableCell>
      <TableCell>
        <div className="flex flex-wrap items-center gap-1">
          <Badge variant={REGISTRATION_STATUS_VARIANTS[status] || "outline"}>
            {t(`activities.registration.status.${status}`)}
          </Badge>
          {registration.cancelled_cause === "payment_expired" && (
            <span className="text-xs text-muted-foreground">{t("activities.registration.expired")}</span>
          )}
          {registration.late_payment_at && (
            <Badge variant="destructive">{t("activities.registration.latePayment")}</Badge>
          )}
          {registration.refund_status === "due" && (
            <Badge variant="outline">{t("activities.registration.refundDue")}</Badge>
          )}
          {registration.refund_status === "returned" && (
            <Badge variant="secondary">{t("activities.registration.refundReturned")}</Badge>
          )}
        </div>
      </TableCell>
      <TableCell>
        <PaymentCell registration={registration} canOpenReceipt={has("billing.read")} />
      </TableCell>
      <TableCell className="text-sm">{formatDate(registration.created_at)}</TableCell>
      <TableCell>
        <div className="flex flex-wrap items-center gap-2">
          {status !== "cancelled" && (
            <Select value="" onValueChange={handleStatusChange}>
              <SelectTrigger className="w-36 h-8 text-xs">
                <SelectValue placeholder={t("activities.registration.changeStatus")} />
              </SelectTrigger>
              <SelectContent>
                {targets.map((target) => (
                  <SelectItem key={target} value={target}>
                    {t(`activities.registration.status.${target}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          {status === "pending" && has("billing.write") && (
            <Button size="sm" variant="outline" className="h-8 text-xs" onClick={handleWaive}>
              {t("activities.registration.confirmWithoutPayment")}
            </Button>
          )}
        </div>
        {confirmDialog}
        <CancelPaidSeatDialog
          open={cancellingPaid}
          onOpenChange={setCancellingPaid}
          onConfirm={(keepPayment) => {
            setCancellingPaid(false);
            changeStatus("cancelled", keepPayment);
          }}
        />
      </TableCell>
    </TableRow>
  );
}

function PaymentCell({
  registration,
  canOpenReceipt,
}: {
  registration: RegistrationData;
  canOpenReceipt: boolean;
}) {
  const t = useTranslations();
  const { shortDateTime: formatDate } = useLocaleDate();
  const receiptStatus = registration.receipt_status;
  if (!receiptStatus || registration.receipt_id == null) {
    return <span className="text-sm text-muted-foreground">—</span>;
  }
  const label = t(`receipts.status${receiptStatus.charAt(0).toUpperCase() + receiptStatus.slice(1)}`);
  const badge = (
    <Badge variant={RECEIPT_STATUS_VARIANTS[receiptStatus] || "outline"}>{label}</Badge>
  );
  return (
    <div className="space-y-0.5">
      {canOpenReceipt ? (
        <Link
          href={`/receipts/${registration.receipt_id}`}
          aria-label={t("activities.registration.openReceipt")}
        >
          {badge}
        </Link>
      ) : (
        badge
      )}
      {registration.status === "pending" && registration.payment_due_at && (
        <p className="text-xs text-muted-foreground">
          {t("activities.registration.payBy", { date: formatDate(registration.payment_due_at) })}
        </p>
      )}
    </div>
  );
}

/** Cancelling a seat that was paid for: does the club return the money? */
export function CancelPaidSeatDialog({
  open,
  onOpenChange,
  onConfirm,
  confirmLabel,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (keepPayment: boolean) => void;
  confirmLabel?: string;
}) {
  const t = useTranslations();
  const [keepPayment, setKeepPayment] = useState(false);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("activities.registration.keepPaymentTitle")}</DialogTitle>
          <DialogDescription>{t("activities.registration.keepPaymentDescription")}</DialogDescription>
        </DialogHeader>
        <label className="flex items-center gap-2 text-sm">
          <Checkbox checked={keepPayment} onCheckedChange={(c) => setKeepPayment(c === true)} />
          {t("activities.registration.keepPayment")}
        </label>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("common.back")}
          </Button>
          <Button variant="destructive" onClick={() => onConfirm(keepPayment)}>
            {confirmLabel ?? t("activities.registration.cancelRegistration")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
