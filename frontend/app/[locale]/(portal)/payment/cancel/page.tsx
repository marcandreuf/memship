"use client";

import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useReceiptByStripeSession } from "@/features/receipts/hooks/use-receipts";
import { CircleX } from "lucide-react";

export default function PaymentCancelPage() {
  const t = useTranslations();
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session_id");

  const { data: receipt } = useReceiptByStripeSession(sessionId);

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CircleX className="mx-auto h-12 w-12 text-muted-foreground mb-2" />
          <CardTitle>{t("receipts.paymentCancelTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="text-center space-y-4">
          <p className="text-muted-foreground">
            {t("receipts.paymentCancelMessage")}
          </p>

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
