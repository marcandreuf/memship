"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
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
import { requestPasswordReset, ClientApiError } from "../services/auth-api";

const forgotPasswordSchema = z.object({
  email: z.string().email(),
});

type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>;

export function ForgotPasswordForm() {
  const t = useTranslations();
  const [submitted, setSubmitted] = useState(false);
  const [resetToken, setResetToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: "" },
  });

  async function onSubmit(data: ForgotPasswordFormValues) {
    setError(null);
    setIsSubmitting(true);
    try {
      const result = await requestPasswordReset(data.email);
      setSubmitted(true);
      setResetToken(result.reset_token);
    } catch (e) {
      setError(
        e instanceof ClientApiError ? e.message : t("auth.resetError")
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">{t("auth.resetSent")}</CardTitle>
          <CardDescription>{t("auth.resetSentDescription")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {resetToken && (
            <div className="rounded-md bg-muted p-3 text-sm">
              <p className="font-medium mb-1">{t("auth.devModeToken")}</p>
              <code className="break-all text-xs">{resetToken}</code>
            </div>
          )}
          <Link
            href="/login"
            className="block text-center text-sm text-primary underline-offset-4 hover:underline"
          >
            {t("auth.backToLogin")}
          </Link>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full max-w-md">
      <CardHeader className="text-center">
        <CardTitle className="text-2xl">{t("auth.forgotPassword")}</CardTitle>
        <CardDescription>
          {t("auth.forgotPasswordDescription")}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            {error && (
              <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                {error}
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

            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? t("common.loading") : t("auth.sendResetLink")}
            </Button>

            <Link
              href="/login"
              className="block text-center text-sm text-muted-foreground hover:text-primary underline-offset-4 hover:underline"
            >
              {t("auth.backToLogin")}
            </Link>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
