"use client";

import type { FieldErrors, FieldValues } from "react-hook-form";

interface FormErrorSummaryProps {
  errors: FieldErrors<FieldValues>;
}

export function FormErrorSummary({ errors }: FormErrorSummaryProps) {
  const messages = collectErrors(errors);
  if (messages.length === 0) return null;

  return (
    <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
      <ul className="list-disc list-inside space-y-1">
        {messages.map((msg, i) => (
          <li key={i}>{msg}</li>
        ))}
      </ul>
    </div>
  );
}

function collectErrors(errors: FieldErrors<FieldValues>): string[] {
  const messages: string[] = [];
  for (const value of Object.values(errors)) {
    if (!value) continue;
    if (typeof value.message === "string" && value.message) {
      messages.push(value.message);
    } else if (typeof value === "object") {
      messages.push(...collectErrors(value as FieldErrors<FieldValues>));
    }
  }
  return messages;
}
