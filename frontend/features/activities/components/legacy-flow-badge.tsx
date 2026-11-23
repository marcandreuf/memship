"use client";

import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { PaymentFlow } from "../services/activities-api";

/**
 * Marks an activity, or a space (#603), that predates pay-to-confirm. Nothing on
 * the default flow. `tooltip` replaces the activity wording.
 */
export function LegacyFlowBadge({ flow, tooltip }: { flow: PaymentFlow; tooltip?: string }) {
  const t = useTranslations("activities.legacy");
  if (flow !== "legacy") return null;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge variant="outline" tabIndex={0} className="text-muted-foreground">
          {t("badge")}
        </Badge>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">{tooltip ?? t("tooltip")}</TooltipContent>
    </Tooltip>
  );
}
