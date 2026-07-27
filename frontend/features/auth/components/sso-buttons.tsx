"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { getSsoProviders } from "../services/auth-api";

function GoogleMark() {
  return (
    <svg viewBox="0 0 18 18" className="size-4" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62Z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18Z"
      />
      <path
        fill="#FBBC05"
        d="M3.97 10.72a5.41 5.41 0 0 1 0-3.44V4.95H.96a9 9 0 0 0 0 8.1l3.01-2.33Z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.5.46 3.44 1.35l2.58-2.58C13.46.9 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58Z"
      />
    </svg>
  );
}

function AppleMark() {
  return (
    <svg viewBox="0 0 384 512" className="size-4 fill-current" aria-hidden="true">
      <path d="M318.7 268.7c-.2-36.7 16.4-64.4 50-84.8-18.8-26.9-47.2-41.7-84.7-44.6-35.5-2.8-74.3 20.7-88.5 20.7-15 0-49.4-19.7-76.4-19.7C63.3 141.2 4 184.8 4 273.5q0 39.3 14.4 81.2c12.8 36.7 59 126.7 107.2 125.2 25.2-.6 43-17.9 75.8-17.9 31.8 0 48.3 17.9 76.4 17.9 48.6-.7 90.4-82.5 102.6-119.3-65.2-30.7-61.7-90-61.7-91.9zm-56.6-164.2c27.3-32.4 24.8-61.9 24-72.5-24.1 1.4-52 16.4-67.9 34.9-17.5 19.8-27.8 44.3-25.6 71.9 26.1 2 49.9-11.4 69.5-34.3z" />
    </svg>
  );
}

/**
 * Sign-in buttons for the configured SSO providers.
 *
 * These are plain links, not fetches: the provider handshake is a full browser
 * redirect and the session cookie is set by the backend on the way back.
 */
export function SsoButtons() {
  const t = useTranslations();

  const { data } = useQuery({
    queryKey: ["auth", "sso-providers"],
    queryFn: getSsoProviders,
    staleTime: 60 * 60 * 1000,
    retry: false,
  });

  if (!data?.google && !data?.apple) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="h-px flex-1 bg-border" />
        <span className="text-xs uppercase text-muted-foreground">
          {t("auth.orContinueWith")}
        </span>
        <span className="h-px flex-1 bg-border" />
      </div>

      <div className="space-y-2">
        {data?.google && (
          <Button variant="outline" className="w-full" asChild>
            <a href="/api/v1/auth/oauth/google/login">
              <GoogleMark />
              {t("auth.continueWithGoogle")}
            </a>
          </Button>
        )}

        {data?.apple && (
          <Button variant="outline" className="w-full" asChild>
            <a href="/api/v1/auth/oauth/apple/login">
              <AppleMark />
              {t("auth.continueWithApple")}
            </a>
          </Button>
        )}
      </div>
    </div>
  );
}