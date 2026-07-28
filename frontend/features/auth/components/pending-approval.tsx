"use client";

import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAuth, useResendVerification } from "../hooks/use-auth";
import type { User } from "../services/auth-api";

/**
 * Shown instead of the portal while a member's registration is awaiting admin
 * approval. The backend enforces the same rule (`require_approved_member`), so
 * this screen is the explanation, not the security boundary.
 */
export function PendingApproval({ user }: { user: User }) {
  const t = useTranslations();
  const { logout } = useAuth();
  const { mutateAsync: resend, isPending: isResending } =
    useResendVerification();

  async function handleResend() {
    try {
      await resend(user.email);
      toast.success(t("auth.verificationResent"));
    } catch {
      /* global handler shows the error toast */
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">
            {t("auth.pendingApprovalTitle")}
          </CardTitle>
          <CardDescription>
            {t("auth.pendingApprovalDescription")}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="rounded-md bg-muted p-3 text-sm">
            <p className="font-medium">
              {user.first_name} {user.last_name}
            </p>
            <p className="text-muted-foreground">{user.email}</p>
          </div>

          {!user.email_verified && (
            <div className="space-y-2 rounded-md border border-dashed p-3 text-sm">
              <p>{t("auth.emailNotVerifiedNotice")}</p>
              <Button
                variant="outline"
                size="sm"
                disabled={isResending}
                onClick={handleResend}
              >
                {t("auth.resendVerification")}
              </Button>
            </div>
          )}

          <Button variant="outline" className="w-full" onClick={() => logout()}>
            {t("nav.logout")}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}