"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card, CardContent, CardHeader, CardTitle,
} from "@/components/ui/card";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { DetailHeader } from "@/components/entity/detail-header";
import { DetailSection } from "@/components/entity/detail-section";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { DetailSkeleton } from "@/components/ui/skeletons";
import { Textarea } from "@/components/ui/textarea";
import { useFormatters } from "@/hooks/use-formatters";
import { toast } from "sonner";
import {
  useRemittance,
  useGenerateRemittanceXml,
  useMarkRemittanceSubmitted,
  useImportRemittanceReturns,
  useCloseRemittance,
  useCancelRemittance,
} from "@/features/remittances/hooks/use-remittances";
import type { ImportReturnResult } from "@/features/remittances/services/remittances-api";

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  draft: "outline",
  ready: "secondary",
  submitted: "secondary",
  processed: "default",
  closed: "default",
  cancelled: "destructive",
};

const RECEIPT_STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  emitted: "secondary",
  paid: "default",
  returned: "destructive",
  overdue: "destructive",
  cancelled: "destructive",
};

export default function RemittanceDetailPage() {
  const t = useTranslations();
  const { id } = useParams<{ id: string }>();
  const { data: remittance, isLoading } = useRemittance(Number(id));
  const [confirmDialog, confirmAction] = useConfirmDialog();
  const [importOpen, setImportOpen] = useState(false);
  const [importResult, setImportResult] = useState<ImportReturnResult | null>(null);

  const generateXmlMutation = useGenerateRemittanceXml();
  const markSubmittedMutation = useMarkRemittanceSubmitted();
  const closeMutation = useCloseRemittance();
  const cancelMutation = useCancelRemittance();

  const { formatCurrency, formatDate } = useFormatters();

  if (isLoading) return <DetailSkeleton />;
  if (!remittance) return <p className="text-center py-8">Remittance not found</p>;

  const statusLabel = t(`remittances.status${remittance.status.charAt(0).toUpperCase() + remittance.status.slice(1)}`);

  const canGenerateXml = ["draft", "ready"].includes(remittance.status);
  const canDownloadXml = remittance.sepa_file_path !== null;
  const canSubmit = remittance.status === "ready";
  const canImportReturns = ["submitted", "processed"].includes(remittance.status);
  const canClose = remittance.status === "processed";
  const canCancel = ["draft", "ready"].includes(remittance.status);
  const isTerminal = ["closed", "cancelled"].includes(remittance.status);

  async function handleGenerateXml() {
    try {
      await generateXmlMutation.mutateAsync(remittance!.id);
      toast.success(t("toast.success.saved"));
    } catch {
      toast.error(t("toast.error.generic"));
    }
  }

  function handleSubmit() {
    confirmAction({
      title: t("remittances.confirmSubmit"),
      cancelLabel: t("common.cancel"),
      confirmLabel: t("remittances.markSubmitted"),
      onConfirm: async () => {
        await markSubmittedMutation.mutateAsync(remittance!.id);
        toast.success(t("toast.success.saved"));
      },
    });
  }

  function handleClose() {
    confirmAction({
      title: t("remittances.confirmClose"),
      cancelLabel: t("common.cancel"),
      confirmLabel: t("remittances.closeRemittance"),
      onConfirm: async () => {
        await closeMutation.mutateAsync(remittance!.id);
        toast.success(t("toast.success.saved"));
      },
    });
  }

  function handleCancel() {
    confirmAction({
      title: t("remittances.confirmCancel"),
      cancelLabel: t("common.cancel"),
      confirmLabel: t("remittances.cancelRemittance"),
      onConfirm: async () => {
        await cancelMutation.mutateAsync(remittance!.id);
        toast.success(t("toast.success.saved"));
      },
    });
  }

  const fields = [
    { label: t("remittances.remittanceNumber"), value: remittance.remittance_number },
    { label: t("remittances.emissionDate"), value: formatDate(remittance.emission_date) },
    { label: t("remittances.dueDate"), value: formatDate(remittance.due_date) },
    { label: t("remittances.receiptCount"), value: String(remittance.receipt_count) },
    { label: t("remittances.totalAmount"), value: formatCurrency(remittance.total_amount) },
    { label: t("remittances.creditor"), value: `${remittance.creditor_name} (${remittance.creditor_id})` },
  ];
  if (remittance.notes) {
    fields.push({ label: t("remittances.notes"), value: remittance.notes });
  }

  return (
    <div className="space-y-4">
      {confirmDialog}

      <DetailHeader
        breadcrumbs={[
          { label: t("remittances.title"), href: "/remittances" },
          { label: remittance.remittance_number },
        ]}
        title={remittance.remittance_number}
        badge={{ label: statusLabel, variant: STATUS_VARIANTS[remittance.status] || "outline" }}
        actions={
          !isTerminal ? (
            <div className="flex gap-2 flex-wrap">
              {canGenerateXml && (
                <Button size="sm" onClick={handleGenerateXml} disabled={generateXmlMutation.isPending}>
                  {t("remittances.generateXml")}
                </Button>
              )}
              {canDownloadXml && (
                <Button size="sm" variant="outline" asChild>
                  <a href={`/api/remittances/${remittance.id}/download-xml`} target="_blank" rel="noopener noreferrer">
                    {t("remittances.downloadXml")}
                  </a>
                </Button>
              )}
              {canSubmit && (
                <Button size="sm" onClick={handleSubmit}>{t("remittances.markSubmitted")}</Button>
              )}
              {canImportReturns && (
                <Button size="sm" variant="outline" onClick={() => setImportOpen(true)}>
                  {t("remittances.importReturns")}
                </Button>
              )}
              {canClose && (
                <Button size="sm" onClick={handleClose}>{t("remittances.closeRemittance")}</Button>
              )}
              {canCancel && (
                <Button size="sm" variant="destructive" onClick={handleCancel}>{t("remittances.cancelRemittance")}</Button>
              )}
            </div>
          ) : undefined
        }
      />

      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-base">{t("remittances.detail")}</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4 pt-0">
          <DetailSection fields={fields} columns={2} />
        </CardContent>
      </Card>

      {/* Receipts in batch */}
      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-base">{t("remittances.receipts")}</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4 pt-0">
          {remittance.receipts && remittance.receipts.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("receipts.receiptNumber")}</TableHead>
                  <TableHead>{t("receipts.description")}</TableHead>
                  <TableHead className="text-right">{t("receipts.total")}</TableHead>
                  <TableHead>{t("receipts.status")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {remittance.receipts.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-mono text-sm">{r.receipt_number}</TableCell>
                    <TableCell className="max-w-[250px] truncate">{r.description}</TableCell>
                    <TableCell className="text-right font-mono">{formatCurrency(r.total_amount)}</TableCell>
                    <TableCell>
                      <Badge variant={RECEIPT_STATUS_VARIANTS[r.status] || "outline"}>
                        {r.status}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-muted-foreground">{t("remittances.noReceipts")}</p>
          )}
        </CardContent>
      </Card>

      {/* Import Returns Dialog */}
      <Dialog open={importOpen} onOpenChange={(open) => { setImportOpen(open); if (!open) setImportResult(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("remittances.importReturnsTitle")}</DialogTitle>
          </DialogHeader>
          {importResult ? (
            <div className="space-y-3">
              <h3 className="text-sm font-medium">{t("remittances.importResults")}</h3>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="border rounded-md p-3">
                  <p className="text-2xl font-bold">{importResult.processed}</p>
                  <p className="text-xs text-muted-foreground">{t("remittances.importProcessed")}</p>
                </div>
                <div className="border rounded-md p-3">
                  <p className="text-2xl font-bold text-destructive">{importResult.returned}</p>
                  <p className="text-xs text-muted-foreground">{t("remittances.importReturned")}</p>
                </div>
                <div className="border rounded-md p-3">
                  <p className="text-2xl font-bold">{importResult.not_found}</p>
                  <p className="text-xs text-muted-foreground">{t("remittances.importNotFound")}</p>
                </div>
              </div>
              <Button variant="outline" className="w-full" onClick={() => { setImportOpen(false); setImportResult(null); }}>
                {t("common.close")}
              </Button>
            </div>
          ) : (
            <ImportReturnsForm
              t={t}
              remittanceId={remittance.id}
              onResult={setImportResult}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ImportReturnsForm({
  t,
  remittanceId,
  onResult,
}: {
  t: (key: string) => string;
  remittanceId: number;
  onResult: (result: ImportReturnResult) => void;
}) {
  const mutation = useImportRemittanceReturns();
  const [jsonText, setJsonText] = useState("");

  async function handleImport() {
    try {
      const data = JSON.parse(jsonText);
      if (!Array.isArray(data)) throw new Error("Expected array");
      const result = await mutation.mutateAsync({ id: remittanceId, data });
      onResult(result);
    } catch {
      toast.error(t("toast.error.generic"));
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">{t("remittances.importReturnsDesc")}</p>
      <Textarea
        value={jsonText}
        onChange={(e) => setJsonText(e.target.value)}
        rows={6}
        className="font-mono text-sm"
        placeholder={'[\n  {"receipt_number": "FAC-2026-0001", "reason": "Insufficient funds"}\n]'}
      />
      <Button onClick={handleImport} disabled={!jsonText.trim() || mutation.isPending} className="w-full">
        {mutation.isPending ? t("common.loading") : t("remittances.importReturns")}
      </Button>
    </div>
  );
}
