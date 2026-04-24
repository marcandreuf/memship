"use client";

import { useLocale, useTranslations } from "next-intl";
import { Landmark, Smartphone } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
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
  variant = "secondary",
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
  const Icon = method === "bizum" ? Smartphone : Landmark;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant={variant}
          size="icon"
          className={className}
          disabled={initiate.isPending}
          onClick={handleClick}
          aria-label={label}
        >
          <Icon className="h-4 w-4" />
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}
