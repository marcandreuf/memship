"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useRedsysReturnStatus } from "@/features/receipts/hooks/use-receipts";
import { CircleCheck, CircleX, Loader2 } from "lucide-react";

export default function RedsysReturnPage() {
  const t = useTranslations();
  const router = useRouter();
  const searchParams = useSearchParams();
  const receiptIdParam = searchParams.get("receipt_id");
  const outcome = searchParams.get("outcome");
  const receiptId = receiptIdParam ? Number(receiptIdParam) : null;
  const { data, isLoading } = useRedsysReturnStatus(receiptId);

  const isPaid = data?.status === "paid";
  const userCancelled = outcome === "ko";
  const pending = !isPaid && !userCancelled;

  let Icon = Loader2;
  let iconClass = "text-muted-foreground animate-spin";
  if (isPaid) {
    Icon = CircleCheck;
    iconClass = "text-green-500";
  } else if (userCancelled) {
    Icon = CircleX;
    iconClass = "text-muted-foreground";
  }

  let title = t("receipts.paymentProcessing");
  if (isPaid) title = t("receipts.paymentSuccessTitle");
  else if (userCancelled) title = t("receipts.paymentCancelTitle");

  let message = t("receipts.paymentPendingMessage");
  if (isPaid) message = t("receipts.paymentSuccessMessage");
  else if (userCancelled) message = t("receipts.paymentCancelMessage");

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <Icon className={`mx-auto h-12 w-12 mb-2 ${iconClass}`} />
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent className="text-center space-y-4">
          <p className="text-muted-foreground">{message}</p>

          {pending && data && (
            <p className="text-xs text-muted-foreground">
              {data.authoritative_note}
            </p>
          )}

          {data && (
            <div className="text-sm space-y-1">
              <p className="font-mono">{data.receipt_number}</p>
              {data.redsys_auth_code && (
                <p className="text-xs text-muted-foreground">
                  {t("receipts.authCode")}: {data.redsys_auth_code}
                </p>
              )}
            </div>
          )}

          {isLoading && !data && (
            <Loader2 className="mx-auto h-4 w-4 animate-spin text-muted-foreground" />
          )}

          <div className="flex flex-col gap-2 pt-2">
            <Button variant="ghost" onClick={() => router.push("/my-receipts")}>
              {t("receipts.backToReceipts")}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
