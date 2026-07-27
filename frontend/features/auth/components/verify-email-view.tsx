"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Link } from "@/lib/i18n/routing";
import { useResendVerification, useVerifyEmail } from "../hooks/use-auth";

type State = "verifying" | "success" | "error";

export function VerifyEmailView() {
  const t = useTranslations();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [state, setState] = useState<State>(token ? "verifying" : "error");
  const [email, setEmail] = useState("");
  const [resent, setResent] = useState(false);

  const { mutateAsync: verify } = useVerifyEmail();
  const { mutateAsync: resend, isPending: isResending } =
    useResendVerification();

  // Tokens are single-use, so guard against React's double-invoked effects in
  // development — a second call would consume nothing and flip a success to an
  // error.
  const attempted = useRef(false);

  useEffect(() => {
    if (!token || attempted.current) return;
    attempted.current = true;

    verify(token)
      .then(() => setState("success"))
      .catch(() => setState("error"));
  }, [token, verify]);

  async function handleResend() {
    try {
      await resend(email);
      setResent(true);
    } catch {
      /* global handler shows the error toast */
    }
  }

  return (
    <Card className="w-full max-w-md">
      <CardHeader className="text-center">
        <CardTitle className="text-2xl">
          {state === "success"
            ? t("auth.emailVerifiedTitle")
            : state === "verifying"
              ? t("auth.verifyingTitle")
              : t("auth.verificationFailedTitle")}
        </CardTitle>
        <CardDescription>
          {state === "success"
            ? t("auth.emailVerifiedDescription")
            : state === "verifying"
              ? t("common.loading")
              : t("auth.verificationFailedDescription")}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {state === "success" && (
          <Button asChild className="w-full">
            <Link href="/login">{t("auth.loginLink")}</Link>
          </Button>
        )}

        {state === "error" && !resent && (
          <div className="space-y-2">
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t("auth.emailPlaceholder")}
              autoComplete="email"
            />
            <Button
              className="w-full"
              disabled={!email || isResending}
              onClick={handleResend}
            >
              {t("auth.resendVerification")}
            </Button>
          </div>
        )}

        {resent && (
          <div className="rounded-md bg-muted p-3 text-sm">
            {t("auth.verificationResent")}
          </div>
        )}
      </CardContent>
    </Card>
  );
}