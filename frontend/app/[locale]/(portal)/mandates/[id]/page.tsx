"use client";

import { useRef } from "react";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card, CardContent, CardHeader, CardTitle,
} from "@/components/ui/card";
import { DetailHeader } from "@/components/entity/detail-header";
import { DetailSection } from "@/components/entity/detail-section";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { DetailSkeleton } from "@/components/ui/skeletons";
import { useFormatters } from "@/hooks/use-formatters";
import { toast } from "sonner";
import {
  useMandate,
  useCancelMandate,
  useUploadSignedMandate,
} from "@/features/mandates/hooks/use-mandates";

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  active: "default",
  cancelled: "destructive",
  expired: "secondary",
};

export default function MandateDetailPage() {
  const t = useTranslations();
  const { id } = useParams<{ id: string }>();
  const { data: mandate, isLoading } = useMandate(Number(id));
  const [confirmDialog, confirmAction] = useConfirmDialog();
  const cancelMutation = useCancelMandate();
  const uploadMutation = useUploadSignedMandate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { formatDate } = useFormatters();

  if (isLoading) return <DetailSkeleton />;
  if (!mandate) return <p className="text-center py-8">Mandate not found</p>;

  const statusLabel = t(`mandates.status${mandate.status.charAt(0).toUpperCase() + mandate.status.slice(1)}`);
  const isActive = mandate.status === "active";

  function handleCancel() {
    confirmAction({
      title: t("mandates.confirmCancel"),
      cancelLabel: t("common.cancel"),
      confirmLabel: t("mandates.cancelMandate"),
      onConfirm: async () => {
        await cancelMutation.mutateAsync(mandate!.id);
        toast.success(t("toast.success.saved"));
      },
    });
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      await uploadMutation.mutateAsync({ id: mandate!.id, file });
      toast.success(t("toast.success.saved"));
    } catch {
      toast.error(t("toast.error.generic"));
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  const fields = [
    { label: t("mandates.mandateReference"), value: mandate.mandate_reference },
    { label: t("mandates.debtorName"), value: mandate.debtor_name },
    { label: t("mandates.debtorIban"), value: mandate.debtor_iban },
    { label: t("mandates.debtorBic"), value: mandate.debtor_bic || "—" },
    { label: t("mandates.mandateType"), value: t(`mandates.type${mandate.mandate_type === "recurrent" ? "Recurrent" : "OneOff"}`) },
    { label: t("mandates.signatureMethod"), value: t(`mandates.method${mandate.signature_method === "paper" ? "Paper" : "Digital"}`) },
    { label: t("mandates.signedAt"), value: formatDate(mandate.signed_at) },
    { label: t("mandates.creditorId"), value: mandate.creditor_id },
  ];

  if (mandate.cancelled_at) {
    fields.push({ label: t("mandates.cancelledAt"), value: formatDate(mandate.cancelled_at) });
  }
  if (mandate.notes) {
    fields.push({ label: t("mandates.notes"), value: mandate.notes });
  }

  return (
    <div className="space-y-4">
      {confirmDialog}

      <DetailHeader
        breadcrumbs={[
          { label: t("mandates.title"), href: "/mandates" },
          { label: mandate.mandate_reference },
        ]}
        title={mandate.mandate_reference}
        badge={{ label: statusLabel, variant: STATUS_VARIANTS[mandate.status] || "outline" }}
        actions={
          <div className="flex gap-2 flex-wrap">
            <Button size="sm" variant="outline" asChild>
              <a href={`/api/mandates/${mandate.id}/pdf`} target="_blank" rel="noopener noreferrer">
                {t("mandates.downloadPdf")}
              </a>
            </Button>
            {isActive && (
              <>
                <Button size="sm" variant="outline" onClick={() => fileInputRef.current?.click()}>
                  {t("mandates.uploadSigned")}
                </Button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png"
                  className="hidden"
                  onChange={handleFileUpload}
                />
                <Button size="sm" variant="destructive" onClick={handleCancel}>
                  {t("mandates.cancelMandate")}
                </Button>
              </>
            )}
          </div>
        }
      />

      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-base">{t("mandates.detail")}</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4 pt-0">
          <DetailSection fields={fields} columns={2} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-base">{t("mandates.uploadSigned")}</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4 pt-0">
          {mandate.document_path ? (
            <Badge variant="default">{t("mandates.documentUploaded")}</Badge>
          ) : (
            <p className="text-sm text-muted-foreground">{t("mandates.noDocument")}</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
