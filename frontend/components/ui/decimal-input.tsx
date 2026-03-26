"use client";

import { Input } from "@/components/ui/input";
import { forwardRef } from "react";

/**
 * Decimal input that accepts European format (1.234,56).
 *
 * During typing: free input of digits, dots, commas.
 * On blur: normalizes to standard decimal and updates the form value.
 *
 * Works with react-hook-form {...field} spread.
 */
function normalizeDecimal(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return "";

  // Both dots and commas → European (dots=thousands, comma=decimal)
  if (trimmed.includes(",") && trimmed.includes(".")) {
    return trimmed.replace(/\./g, "").replace(",", ".");
  }

  // Only comma → decimal separator
  if (trimmed.includes(",")) {
    return trimmed.replace(",", ".");
  }

  // Only dots: if 3 digits after last dot and short integer part → thousands
  const parts = trimmed.split(".");
  if (parts.length === 2 && parts[1].length === 3) {
    return trimmed.replace(".", "");
  }

  return trimmed;
}

export const DecimalInput = forwardRef<
  HTMLInputElement,
  React.ComponentProps<typeof Input>
>(({ onChange, onBlur, ...props }, ref) => {
  return (
    <Input
      ref={ref}
      inputMode="text"
      {...props}
      onChange={onChange}
      onBlur={(e) => {
        const normalized = normalizeDecimal(e.target.value);
        if (normalized !== e.target.value) {
          e.target.value = normalized;
          // Trigger onChange so react-hook-form picks up the normalized value
          onChange?.({ ...e, target: e.target } as React.ChangeEvent<HTMLInputElement>);
        }
        onBlur?.(e);
      }}
    />
  );
});

DecimalInput.displayName = "DecimalInput";
