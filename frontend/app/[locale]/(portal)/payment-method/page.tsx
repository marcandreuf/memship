"use client";

import { useEffect } from "react";
import { useRouter } from "@/lib/i18n/routing";

// Payment method moved into the profile page as a tab; keep the old URL
// working for bookmarks and any future deep links.
export default function PaymentMethodRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/profile?tab=payment");
  }, [router]);
  return null;
}
