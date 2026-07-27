import { Suspense } from "react";
import { VerifyEmailView } from "@/features/auth/components/verify-email-view";

export default function VerifyEmailPage() {
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Suspense>
        <VerifyEmailView />
      </Suspense>
    </div>
  );
}