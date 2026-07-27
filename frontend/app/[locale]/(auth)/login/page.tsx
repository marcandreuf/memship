import { Suspense } from "react";
import { LoginForm } from "@/features/auth/components/login-form";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      {/* LoginForm reads the ?error= code an SSO redirect can carry. */}
      <Suspense>
        <LoginForm />
      </Suspense>
    </div>
  );
}
