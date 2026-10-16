"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useRef, useState, type ReactNode } from "react";
import { toast } from "sonner";
import { getErrorMessage } from "./errors";

export function ReactQueryProvider({ children }: { children: ReactNode }) {
  // The client is built once; read the translator through a ref so the
  // handler follows a locale change rather than keeping the first one.
  const t = useTranslations();
  const tRef = useRef(t);
  tRef.current = t;

  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
          mutations: {
            // The one place a failed mutation is reported. It used to sit
            // beside a `toast.error` in fourteen components' own `catch`
            // blocks, and every failed save raised two identical toasts
            // (#378). A mutation with no handling of its own must still say
            // something, which is the point of #367.
            //
            // It stays a *default* deliberately. A hook that declares its own
            // `onError` replaces this one, which is how a screen that renders
            // the failure itself opts out — see `useScanCard`, where the
            // global toast repeated the panel's message in the API's English
            // (#287). A `MutationCache` handler would fire *in addition* to
            // the hook's and silently undo every one of those opt-outs.
            onError: (error) => {
              toast.error(getErrorMessage(error, tRef.current));
            },
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
