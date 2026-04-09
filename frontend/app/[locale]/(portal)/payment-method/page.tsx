"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Card, CardContent, CardHeader, CardTitle, CardDescription,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { AlertTriangle } from "lucide-react";
import { FormSkeleton } from "@/components/ui/skeletons";
import { apiClient } from "@/lib/client-api";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

interface PaymentMethodData {
  payment_method: string | null;
  bank_iban: string | null;
  bank_iban_masked: string | null;
  bank_bic: string | null;
  bank_holder_name: string | null;
  mandate_status: string | null;
  mandate_reference: string | null;
  mandate_signed_at: string | null;
  warnings: string[];
}

const METHODS = ["direct_debit", "bank_transfer", "cash", "card"] as const;

function usePaymentMethod() {
  return useQuery({
    queryKey: ["payment-method"],
    queryFn: () => apiClient<PaymentMethodData>("/members/me/payment-method"),
  });
}

function useUpdatePaymentMethod() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      apiClient<PaymentMethodData>("/members/me/payment-method", {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["payment-method"] }),
  });
}

export default function PaymentMethodPage() {
  const t = useTranslations();
  const { data, isLoading } = usePaymentMethod();
  const mutation = useUpdatePaymentMethod();

  const [method, setMethod] = useState<string>("");
  const [iban, setIban] = useState("");
  const [bic, setBic] = useState("");
  const [holderName, setHolderName] = useState("");
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (data) {
      setMethod(data.payment_method || "");
      setIban(data.bank_iban || "");
      setBic(data.bank_bic || "");
      setHolderName(data.bank_holder_name || "");
    }
  }, [data]);

  if (isLoading) return <FormSkeleton fields={4} />;

  function handleChange<T>(setter: (v: T) => void) {
    return (value: T) => {
      setter(value);
      setDirty(true);
    };
  }

  async function handleSave() {
    try {
      await mutation.mutateAsync({
        payment_method: method || null,
        bank_iban: iban || null,
        bank_bic: bic || null,
        bank_holder_name: holderName || null,
      });
      toast.success(t("paymentMethod.saved"));
      setDirty(false);
    } catch {
      toast.error(t("toast.error.generic"));
    }
  }

  const warningKeys: Record<string, string> = {
    missing_iban: "paymentMethod.warningMissingIban",
    invalid_iban: "paymentMethod.warningInvalidIban",
    missing_bic: "paymentMethod.warningMissingBic",
    no_active_mandate: "paymentMethod.warningNoMandate",
  };

  const mandateStatusLabels: Record<string, string> = {
    active: "paymentMethod.mandateActive",
    cancelled: "paymentMethod.mandateCancelled",
    expired: "paymentMethod.mandateExpired",
    none: "paymentMethod.mandateNone",
  };

  const mandateStatusVariants: Record<string, "default" | "destructive" | "secondary" | "outline"> = {
    active: "default",
    cancelled: "destructive",
    expired: "secondary",
    none: "outline",
  };

  return (
    <div className="space-y-4 max-w-2xl">
      <h1 className="text-2xl font-bold">{t("paymentMethod.title")}</h1>

      {/* Warnings */}
      {data?.warnings && data.warnings.length > 0 && (
        <Card className="border-yellow-300 bg-yellow-50 dark:bg-yellow-950/20 dark:border-yellow-800">
          <CardContent className="py-3 px-4">
            <ul className="space-y-1">
              {data.warnings.map((w) => (
                <li key={w} className="flex items-center gap-2 text-sm text-yellow-800 dark:text-yellow-200">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  {t(warningKeys[w] || w)}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Payment method selector */}
      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-base">{t("paymentMethod.currentMethod")}</CardTitle>
          <CardDescription className="text-xs">{t("paymentMethod.selectMethod")}</CardDescription>
        </CardHeader>
        <CardContent className="px-4 pb-4 pt-0">
          <div className="grid gap-2 sm:grid-cols-2">
            {METHODS.map((m) => {
              const labelKey = m === "direct_debit" ? "directDebit" : m === "bank_transfer" ? "bankTransfer" : m;
              const isSelected = method === m;
              return (
                <button
                  key={m}
                  type="button"
                  onClick={() => handleChange(setMethod)(m)}
                  className={`text-left rounded-lg border p-3 transition-colors ${
                    isSelected
                      ? "border-primary bg-primary/5 ring-1 ring-primary"
                      : "border-border hover:border-primary/50"
                  }`}
                >
                  <p className="text-sm font-medium">{t(`paymentMethod.${labelKey}`)}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{t(`paymentMethod.${labelKey}Desc`)}</p>
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Bank details — shown when direct_debit or bank_transfer */}
      {(method === "direct_debit" || method === "bank_transfer") && (
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-base">{t("paymentMethod.bankDetails")}</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 pt-0 space-y-3">
            <div>
              <Label className="text-xs">{t("paymentMethod.holderName")}</Label>
              <Input className="h-8 mt-1" value={holderName} onChange={(e) => handleChange(setHolderName)(e.target.value)} />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label className="text-xs">{t("paymentMethod.iban")}</Label>
                <Input className="h-8 mt-1 font-mono" value={iban} onChange={(e) => handleChange(setIban)(e.target.value)} placeholder="ES9121000418450200051332" />
              </div>
              <div>
                <Label className="text-xs">{t("paymentMethod.bic")}</Label>
                <Input className="h-8 mt-1 font-mono" value={bic} onChange={(e) => handleChange(setBic)(e.target.value)} placeholder="CAIXESBBXXX" />
                <p className="text-xs text-muted-foreground mt-1">{t("paymentMethod.bicHint")}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Mandate info — shown when direct_debit */}
      {method === "direct_debit" && data?.mandate_status && (
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-base">{t("paymentMethod.mandate")}</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 pt-0">
            <dl className="grid gap-2 sm:grid-cols-2">
              <div className="flex flex-col gap-0.5">
                <dt className="text-xs text-muted-foreground">{t("paymentMethod.mandateStatus")}</dt>
                <dd>
                  <Badge variant={mandateStatusVariants[data.mandate_status] || "outline"}>
                    {t(mandateStatusLabels[data.mandate_status] || data.mandate_status)}
                  </Badge>
                </dd>
              </div>
              {data.mandate_reference && (
                <div className="flex flex-col gap-0.5">
                  <dt className="text-xs text-muted-foreground">{t("paymentMethod.mandateReference")}</dt>
                  <dd className="text-sm font-mono">{data.mandate_reference}</dd>
                </div>
              )}
              {data.mandate_signed_at && (
                <div className="flex flex-col gap-0.5">
                  <dt className="text-xs text-muted-foreground">{t("paymentMethod.mandateSignedAt")}</dt>
                  <dd className="text-sm">{new Date(data.mandate_signed_at).toLocaleDateString()}</dd>
                </div>
              )}
            </dl>
          </CardContent>
        </Card>
      )}

      {dirty && (
        <Button onClick={handleSave} disabled={mutation.isPending}>
          {mutation.isPending ? t("common.loading") : t("common.save")}
        </Button>
      )}
    </div>
  );
}
