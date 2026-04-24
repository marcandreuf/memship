"use client";

import { useLocale, useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useRedsysInitiate } from "@/features/receipts/hooks/use-receipts";
import type {
  RedsysInitiateResponse,
  RedsysLocale,
  RedsysMethod,
} from "@/features/receipts/services/receipts-api";

interface RedsysPayButtonProps {
  receiptId: number;
  method?: RedsysMethod;
  variant?: "default" | "secondary" | "outline";
  size?: "default" | "sm" | "lg";
  className?: string;
}

function toRedsysLocale(locale: string): RedsysLocale {
  if (locale === "ca" || locale === "en") return locale;
  return "es";
}

function submitHiddenForm(response: RedsysInitiateResponse) {
  const form = document.createElement("form");
  form.method = "POST";
  form.action = response.redirect_url;
  form.style.display = "none";
  for (const [key, value] of Object.entries(response.form_params)) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = key;
    input.value = value;
    form.appendChild(input);
  }
  document.body.appendChild(form);
  form.submit();
}

export function RedsysPayButton({
  receiptId,
  method = "card",
  variant = "default",
  size = "sm",
  className,
}: RedsysPayButtonProps) {
  const t = useTranslations();
  const locale = useLocale();
  const initiate = useRedsysInitiate();

  async function handleClick() {
    try {
      const result = await initiate.mutateAsync({
        receiptId,
        method,
        locale: toRedsysLocale(locale),
      });
      toast.info(t("receipts.redirectingToPayment"));
      submitHiddenForm(result);
    } catch {
      /* toast handled by global mutation error handler */
    }
  }

  const label =
    method === "bizum"
      ? t("receipts.payWithBizum")
      : t("receipts.payWithRedsys");

  return (
    <Button
      type="button"
      variant={variant}
      size={size}
      className={className}
      disabled={initiate.isPending}
      onClick={handleClick}
    >
      {initiate.isPending ? t("common.loading") : label}
    </Button>
  );
}
