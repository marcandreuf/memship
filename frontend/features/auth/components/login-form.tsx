"use client";

import { useForm } from "react-hook-form";
import { useZodResolver } from "@/hooks/use-zod-resolver";
import { z } from "zod";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Link } from "@/lib/i18n/routing";
import { useAuth } from "../hooks/use-auth";
import { useSearchParams } from "next/navigation";
import { ClientApiError } from "../services/auth-api";
import { SsoButtons } from "./sso-buttons";

// Codes the backend appends when an SSO handshake cannot complete.
const SSO_ERROR_KEYS: Record<string, string> = {
  sso_failed: "auth.ssoFailed",
  sso_email_unverified: "auth.ssoEmailUnverified",
  registration_closed: "auth.ssoRegistrationClosed",
  account_disabled: "auth.ssoAccountDisabled",
  account_locked: "auth.ssoAccountLocked",
};

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export function LoginForm() {
  const t = useTranslations();
  const { login, isLoggingIn, loginError } = useAuth();
  const searchParams = useSearchParams();

  const form = useForm<LoginFormValues>({
    resolver: useZodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  async function onSubmit(data: LoginFormValues) {
    try {
      await login(data);
    } catch {
      // Error is captured in loginError
    }
  }

  const ssoErrorKey = SSO_ERROR_KEYS[searchParams.get("error") ?? ""];

  const errorMessage =
    loginError instanceof ClientApiError
      ? loginError.message
      : loginError
        ? t("auth.loginError")
        : ssoErrorKey
          ? t(ssoErrorKey)
          : null;

  return (
    <Card className="w-full max-w-md">
      <CardHeader className="text-center">
        <CardTitle className="text-2xl">{t("auth.login")}</CardTitle>
        <CardDescription>{t("auth.loginDescription")}</CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            {errorMessage && (
              <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                {errorMessage}
              </div>
            )}

            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("auth.email")}</FormLabel>
                  <FormControl>
                    <Input
                      type="email"
                      placeholder={t("auth.emailPlaceholder")}
                      autoComplete="email"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("auth.password")}</FormLabel>
                  <FormControl>
                    <Input
                      type="password"
                      placeholder={t("auth.passwordPlaceholder")}
                      autoComplete="current-password"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <Button type="submit" className="w-full" disabled={isLoggingIn}>
              {isLoggingIn ? t("common.loading") : t("auth.login")}
            </Button>

            <SsoButtons />

            <div className="text-center text-sm space-y-2">
              <Link
                href="/forgot-password"
                className="text-muted-foreground hover:text-primary underline-offset-4 hover:underline"
              >
                {t("auth.forgotPassword")}
              </Link>
              <p className="text-muted-foreground">
                {t("auth.noAccount")}{" "}
                <Link
                  href="/register"
                  className="text-primary underline-offset-4 hover:underline"
                >
                  {t("auth.registerLink")}
                </Link>
              </p>
            </div>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
