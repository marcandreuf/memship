"use client";

import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { PasswordInput } from "@/components/ui/password-input";
import { cn } from "@/lib/utils";

interface StoredSecretFieldProps {
  name: string;
  stored: boolean;
  last4: string | null;
  replacing: boolean;
  value: string;
  cleared?: boolean;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
  onReplace: () => void;
  onCancel: () => void;
  onChange: (value: string) => void;
}

// A stored secret renders as text, not as an input: a password manager has no
// field to fill, and a filled box can no longer hide that a value is on file.
// The input exists only once the admin asks to replace it, and only a value
// typed into it is a deliberate write.
export function StoredSecretField({
  name,
  stored,
  last4,
  replacing,
  value,
  cleared = false,
  disabled,
  placeholder,
  className,
  onReplace,
  onCancel,
  onChange,
}: StoredSecretFieldProps) {
  const t = useTranslations();

  if (stored && !replacing) {
    return (
      <div className="flex items-center gap-2">
        <div
          data-testid={`${name}-stored`}
          className="flex h-8 flex-1 items-center gap-2 rounded-md border bg-muted/40 px-3 font-mono text-xs"
        >
          <span className={cn(cleared && "text-muted-foreground line-through")}>
            {`•••• ${last4 ?? ""}`}
          </span>
          <span className="font-sans text-muted-foreground">
            ({t("settings.secretField.stored")})
          </span>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8"
          disabled={disabled || cleared}
          onClick={onReplace}
        >
          {t("settings.secretField.replace")}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1">
        <PasswordInput
          name={name}
          autoComplete="new-password"
          data-1p-ignore
          data-lpignore="true"
          className={className}
          placeholder={placeholder}
          value={value}
          disabled={disabled}
          autoFocus={stored}
          onChange={(e) => onChange(e.target.value)}
        />
      </div>
      {stored && (
        <Button type="button" variant="ghost" size="sm" className="h-8" onClick={onCancel}>
          {t("common.cancel")}
        </Button>
      )}
    </div>
  );
}
