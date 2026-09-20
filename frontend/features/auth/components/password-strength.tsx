"use client";

import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";

const LEVELS = ["weak", "fair", "good", "strong"] as const;

const LEVEL_COLORS = [
  "bg-destructive",
  "bg-amber-500",
  "bg-amber-500",
  "bg-primary",
] as const;

// Local heuristic on purpose — a zxcvbn-style dictionary check would add
// ~800 KB to the auth bundle for an informational bar. The Zod schema still
// owns the hard rule (min 8), so anything shorter shows an empty bar.
export function scorePassword(password: string): number {
  if (password.length < 8) return 0;
  let score = 1;
  if (password.length >= 12) score++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
  if (/\d/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;
  return Math.min(score, LEVELS.length);
}

export function PasswordStrength({ password }: { password: string }) {
  const t = useTranslations();
  const score = scorePassword(password);
  const level = score > 0 ? LEVELS[score - 1] : null;

  return (
    <div className="space-y-1" data-testid="password-strength">
      <div className="flex gap-1" aria-hidden>
        {LEVELS.map((_, i) => (
          <div
            key={i}
            className={cn(
              "h-1 flex-1 rounded-full bg-muted transition-colors",
              i < score && LEVEL_COLORS[score - 1]
            )}
          />
        ))}
      </div>
      <p className="min-h-4 text-xs text-muted-foreground" aria-live="polite">
        {level && t(`auth.passwordStrength.${level}`)}
      </p>
    </div>
  );
}
