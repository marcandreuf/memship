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
