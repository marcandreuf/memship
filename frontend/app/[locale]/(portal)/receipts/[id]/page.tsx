"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DecimalInput } from "@/components/ui/decimal-input";
import {
  Card, CardContent, CardHeader, CardTitle,
} from "@/components/ui/card";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { DetailHeader } from "@/components/entity/detail-header";
import { DetailSection } from "@/components/entity/detail-section";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { DetailSkeleton } from "@/components/ui/skeletons";
import { useFormatters } from "@/hooks/use-formatters";
import { toast } from "sonner";
import {
  useReceipt,
  useUpdateReceipt,
  useEmitReceipt,
  usePayReceipt,
  useCancelReceipt,
  useReturnReceipt,
  useReemitReceipt,
  useStripeCheckout,
} from "@/features/receipts/hooks/use-receipts";

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  new: "outline",
  pending: "secondary",
  emitted: "secondary",
  paid: "default",
  returned: "destructive",
  cancelled: "destructive",
  overdue: "destructive",
};

export default function ReceiptDetailPage() {
  const t = useTranslations();
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const { data: receipt, isLoading } = useReceipt(Number(id));
  const [editOpen, setEditOpen] = useState(false);
  const [payOpen, setPayOpen] = useState(false);
  const [returnOpen, setReturnOpen] = useState(false);
  const [payMethod, setPayMethod] = useState("");
  const [payDate, setPayDate] = useState(new Date().toISOString().split("T")[0]);
  const [returnReason, setReturnReason] = useState("");
  const [confirmDialog, confirmAction] = useConfirmDialog();

  const { formatCurrency, formatDate } = useFormatters();
  const updateMutation = useUpdateReceipt();
  const emitMutation = useEmitReceipt();
  const payMutation = usePayReceipt();
  const cancelMutation = useCancelReceipt();
  const returnMutation = useReturnReceipt();
  const reemitMutation = useReemitReceipt();
  const stripeCheckoutMutation = useStripeCheckout();

  if (isLoading) return <DetailSkeleton />;
  if (!receipt) return <p className="text-center py-8">Receipt not found</p>;

  const statusLabel = t(`receipts.status${receipt.status.charAt(0).toUpperCase() + receipt.status.slice(1)}`);

  function handleEmit() {
    confirmAction({
      title: t("receipts.confirmEmit"),
      cancelLabel: t("common.cancel"),
      confirmLabel: t("receipts.emit"),
      onConfirm: async () => {
        await emitMutation.mutateAsync(receipt!.id);
        toast.success(t("toast.success.saved"));
      },
    });
  }

  function handleCancel() {
    confirmAction({
      title: t("receipts.confirmCancel"),
      cancelLabel: t("common.cancel"),
      confirmLabel: t("receipts.cancel"),
      onConfirm: async () => {
        await cancelMutation.mutateAsync(receipt!.id);
        toast.success(t("toast.success.saved"));
      },
    });
  }

  function handleReemit() {
    confirmAction({
      title: t("receipts.confirmReemit"),
      cancelLabel: t("common.cancel"),
      confirmLabel: t("receipts.reemit"),
      onConfirm: async () => {
        await reemitMutation.mutateAsync(receipt!.id);
        toast.success(t("toast.success.saved"));
      },
    });
  }

  async function handlePay() {
    if (!payMethod) return;
    try {
      await payMutation.mutateAsync({ id: receipt!.id, data: { payment_method: payMethod, payment_date: payDate || undefined } });
      toast.success(t("toast.success.saved"));
      setPayOpen(false);
    } catch { /* global handler */ }
  }

  async function handleReturn() {
    if (!returnReason.trim()) return;
    try {
      await returnMutation.mutateAsync({ id: receipt!.id, data: { return_reason: returnReason } });
      toast.success(t("toast.success.saved"));
      setReturnOpen(false);
    } catch { /* global handler */ }
  }

  async function handlePayOnline() {
    try {
      const result = await stripeCheckoutMutation.mutateAsync(receipt!.id);
      window.location.href = result.redirect_url;
    } catch { /* global handler */ }
  }

  const canEdit = ["new", "pending"].includes(receipt.status);
  const canEmit = ["new", "pending"].includes(receipt.status);
  const canPay = ["emitted", "overdue"].includes(receipt.status);
  const canReturn = ["emitted", "overdue"].includes(receipt.status);
  const canCancel = !["paid", "cancelled"].includes(receipt.status);
  const canReemit = receipt.status === "returned";

  const fields = [
    { label: t("receipts.receiptNumber"), value: receipt.receipt_number },
    { label: t("receipts.member"), value: receipt.member_name || "—" },
    { label: t("receipts.description"), value: receipt.description },
    { label: t("receipts.origin"), value: t(`receipts.origin${receipt.origin.charAt(0).toUpperCase() + receipt.origin.slice(1)}`) },
    { label: t("receipts.base"), value: formatCurrency(receipt.base_amount) },
    { label: t("receipts.vatRate"), value: `${Number(receipt.vat_rate)}%` },
    { label: t("receipts.vat"), value: formatCurrency(receipt.vat_amount) },
    { label: t("receipts.total"), value: formatCurrency(receipt.total_amount) },
    { label: t("receipts.emissionDate"), value: formatDate(receipt.emission_date) },
    { label: t("receipts.dueDate"), value: formatDate(receipt.due_date) },
  ];

  if (receipt.payment_method) {
    fields.push({ label: t("receipts.paymentMethod"), value: t(`receipts.method${receipt.payment_method.split("_").map((w: string) => w.charAt(0).toUpperCase() + w.slice(1)).join("")}`) });
    fields.push({ label: t("receipts.paymentDate"), value: formatDate(receipt.payment_date) });
  }

  if (receipt.return_reason) {
    fields.push({ label: t("receipts.returnReason"), value: receipt.return_reason });
    fields.push({ label: t("receipts.returnDate"), value: formatDate(receipt.return_date) });
  }

  if (receipt.billing_period_start) {
    fields.push({ label: t("receipts.billingPeriod"), value: `${formatDate(receipt.billing_period_start)} — ${formatDate(receipt.billing_period_end)}` });
  }

  if (receipt.notes) {
    fields.push({ label: t("receipts.notes"), value: receipt.notes });
  }

  return (
    <div className="space-y-4">
      {confirmDialog}

      <DetailHeader
        breadcrumbs={[
          { label: t("receipts.title"), href: "/receipts" },
          { label: receipt.receipt_number },
        ]}
        title={receipt.receipt_number}
        badge={{ label: statusLabel, variant: STATUS_VARIANTS[receipt.status] || "outline" }}
        actions={
          <div className="flex gap-2 flex-wrap">
            {canEdit && <Button size="sm" variant="outline" onClick={() => setEditOpen(true)}>{t("common.edit")}</Button>}
            {canEmit && <Button size="sm" onClick={handleEmit}>{t("receipts.emit")}</Button>}
            {canPay && <Button size="sm" onClick={handlePayOnline} disabled={stripeCheckoutMutation.isPending}>{stripeCheckoutMutation.isPending ? t("receipts.redirectingToPayment") : t("receipts.payOnline")}</Button>}
            {canPay && <Button size="sm" variant="outline" onClick={() => setPayOpen(true)}>{t("receipts.markPaid")}</Button>}
            {canReturn && <Button size="sm" variant="outline" onClick={() => setReturnOpen(true)}>{t("receipts.markReturned")}</Button>}
            {canReemit && <Button size="sm" onClick={handleReemit}>{t("receipts.reemit")}</Button>}
            {canCancel && <Button size="sm" variant="destructive" onClick={handleCancel}>{t("receipts.cancel")}</Button>}
            <Button size="sm" variant="outline" asChild>
              <a href={`/api/receipts/${receipt.id}/pdf`} target="_blank" rel="noopener noreferrer">
                {t("receipts.downloadPdf")}
              </a>
            </Button>
          </div>
        }
      />

      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-base">{t("receipts.receiptDetail")}</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4 pt-0">
          <DetailSection fields={fields} columns={2} />
        </CardContent>
      </Card>

      {/* Pay Dialog */}
      <Dialog open={payOpen} onOpenChange={setPayOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("receipts.markPaid")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">{t("receipts.paymentMethod")}</label>
              <Select value={payMethod} onValueChange={setPayMethod}>
                <SelectTrigger><SelectValue placeholder={t("receipts.selectPaymentMethod")} /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="cash">{t("receipts.methodCash")}</SelectItem>
                  <SelectItem value="bank_transfer">{t("receipts.methodBankTransfer")}</SelectItem>
                  <SelectItem value="card">{t("receipts.methodCard")}</SelectItem>
                  <SelectItem value="direct_debit">{t("receipts.methodDirectDebit")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium">{t("receipts.paymentDate")}</label>
              <Input type="date" value={payDate} onChange={(e) => setPayDate(e.target.value)} />
            </div>
            <Button onClick={handlePay} disabled={!payMethod || payMutation.isPending} className="w-full">
              {payMutation.isPending ? t("common.loading") : t("receipts.markPaid")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Return Dialog */}
      <Dialog open={returnOpen} onOpenChange={setReturnOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("receipts.markReturned")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">{t("receipts.returnReason")}</label>
              <Input
                value={returnReason}
                onChange={(e) => setReturnReason(e.target.value)}
                placeholder={t("receipts.enterReturnReason")}
              />
            </div>
            <Button onClick={handleReturn} disabled={!returnReason.trim() || returnMutation.isPending} className="w-full">
              {returnMutation.isPending ? t("common.loading") : t("receipts.markReturned")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("receipts.editReceipt")}</DialogTitle>
          </DialogHeader>
          <EditReceiptForm
            receipt={receipt}
            t={t}
            onSuccess={() => setEditOpen(false)}
            updateMutation={updateMutation}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}

function EditReceiptForm({
  receipt,
  t,
  onSuccess,
  updateMutation,
}: {
  receipt: { id: number; description: string; base_amount: number; vat_rate: number; due_date: string | null; notes: string | null };
  t: (key: string) => string;
  onSuccess: () => void;
  updateMutation: ReturnType<typeof useUpdateReceipt>;
}) {
  const [description, setDescription] = useState(receipt.description);
  const [baseAmount, setBaseAmount] = useState(String(receipt.base_amount));
  const [vatRate, setVatRate] = useState(String(receipt.vat_rate));
  const [dueDate, setDueDate] = useState(receipt.due_date || "");
  const [notes, setNotes] = useState(receipt.notes || "");

  const base = parseFloat(baseAmount) || 0;
  const vat = parseFloat(vatRate) || 0;
  const vatAmount = (base * vat / 100);
  const total = base + vatAmount;

  async function handleSave() {
    const data: Record<string, unknown> = {
      description,
      base_amount: parseFloat(baseAmount),
      vat_rate: parseFloat(vatRate),
    };
    if (dueDate) data.due_date = dueDate;
    if (notes) data.notes = notes;

    try {
      await updateMutation.mutateAsync({ id: receipt!.id, data });
      toast.success(t("toast.success.saved"));
      onSuccess();
    } catch { /* global handler */ }
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm font-medium">{t("receipts.description")}</label>
        <Input value={description} onChange={(e) => setDescription(e.target.value)} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="text-sm font-medium">{t("receipts.base")} (€)</label>
          <DecimalInput value={baseAmount} onChange={(e) => setBaseAmount(e.target.value)} onBlur={(e) => setBaseAmount(e.target.value)} />
        </div>
        <div>
          <label className="text-sm font-medium">{t("receipts.vatRate")} (%)</label>
          <DecimalInput value={vatRate} onChange={(e) => setVatRate(e.target.value)} onBlur={(e) => setVatRate(e.target.value)} />
        </div>
      </div>
      <div className="text-sm text-muted-foreground px-1">
        {t("receipts.vat")}: {vatAmount.toFixed(2)} — {t("receipts.total")}: {total.toFixed(2)}
      </div>
      <div>
        <label className="text-sm font-medium">{t("receipts.dueDate")}</label>
        <Input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
      </div>
      <div>
        <label className="text-sm font-medium">{t("receipts.notes")}</label>
        <Input value={notes} onChange={(e) => setNotes(e.target.value)} />
      </div>
      <Button onClick={handleSave} disabled={!description.trim() || updateMutation.isPending} className="w-full">
        {updateMutation.isPending ? t("common.loading") : t("common.save")}
      </Button>
    </div>
  );
}
