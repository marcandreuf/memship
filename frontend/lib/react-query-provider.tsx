"use client";

import {
  MutationCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useRef, useState, type ReactNode } from "react";
import { toast } from "sonner";
import { getErrorMessage } from "./errors";

declare module "@tanstack/react-query" {
  interface Register {
    mutationMeta: {
      /**
       * Set when the caller renders its own message for a failure, so the
       * handler below stays quiet instead of adding a second, vaguer toast
       * beside it. Use it only where the local message says more than
       * `getErrorMessage` can — naming the fields a provider is missing, say.
       */
      ownErrorMessage?: boolean;
    };
  }
}

export function ReactQueryProvider({ children }: { children: ReactNode }) {
  // The client is built once; read the translator through a ref so the
  // handler follows a locale change rather than keeping the first one.
  const t = useTranslations();
  const tRef = useRef(t);
  tRef.current = t;

  const [queryClient] = useState(
    () =>
      new QueryClient({
        // On the cache rather than `defaultOptions.mutations`, which is not
        // handed the mutation and so cannot read `meta`.
        //
        // This is the one place a failed mutation is reported. It used to sit
        // beside a `toast.error` in fourteen components' own `catch` blocks,
        // and every failed save raised two identical toasts (#378). The net
        // belongs here: a mutation with no local handling must still say
        // something, which is the whole point of #367.
        mutationCache: new MutationCache({
          onError: (error, _variables, _context, mutation) => {
            if (mutation.meta?.ownErrorMessage) return;
            toast.error(getErrorMessage(error, tRef.current));
          },
        }),
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
