"use client";

import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { PaymentFlow } from "../services/activities-api";

/** Marks an activity that predates pay-to-confirm. Nothing on the default flow. */
export function LegacyFlowBadge({ flow }: { flow: PaymentFlow }) {
  const t = useTranslations("activities.legacy");
  if (flow !== "legacy") return null;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge variant="outline" tabIndex={0} className="text-muted-foreground">
          {t("badge")}
        </Badge>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">{t("tooltip")}</TooltipContent>
    </Tooltip>
  );
}
