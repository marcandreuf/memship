"use client";

import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useReceiptByStripeSession } from "@/features/receipts/hooks/use-receipts";
import { useFormatters } from "@/hooks/use-formatters";
import { CircleCheck, Loader2 } from "lucide-react";

export default function PaymentSuccessPage() {
  const t = useTranslations();
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session_id");
  const { formatCurrency } = useFormatters();

  const { data: receipt, isLoading } = useReceiptByStripeSession(sessionId);

  const isPaid = receipt?.status === "paid";

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          {isPaid ? (
            <CircleCheck className="mx-auto h-12 w-12 text-green-500 mb-2" />
          ) : (
            <Loader2 className="mx-auto h-12 w-12 text-muted-foreground animate-spin mb-2" />
          )}
          <CardTitle>
            {isPaid
              ? t("receipts.paymentSuccessTitle")
              : t("receipts.paymentProcessing")}
          </CardTitle>
        </CardHeader>
        <CardContent className="text-center space-y-4">
          <p className="text-muted-foreground">
            {isPaid
              ? t("receipts.paymentSuccessMessage")
              : t("receipts.paymentPendingMessage")}
          </p>

          {receipt && (
            <div className="text-sm space-y-1">
              <p className="font-mono">{receipt.receipt_number}</p>
              <p className="font-semibold text-lg">{formatCurrency(receipt.total_amount)}</p>
            </div>
          )}

          <div className="flex flex-col gap-2 pt-2">
            {receipt && (
              <Button variant="outline" onClick={() => router.push(`/my-receipts`)}>
                {t("receipts.viewReceipt")}
              </Button>
            )}
            <Button variant="ghost" onClick={() => router.push("/my-receipts")}>
              {t("receipts.backToReceipts")}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
