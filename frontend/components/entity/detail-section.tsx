"use client";

import { type ReactNode } from "react";

interface DetailField {
  label: string;
  value: ReactNode;
  inline?: boolean;
}

interface DetailSectionProps {
  fields: DetailField[];
  columns?: 2 | 3;
}

export function DetailSection({ fields, columns = 2 }: DetailSectionProps) {
  const gridClass =
    columns === 3
      ? "grid gap-x-4 gap-y-2 sm:grid-cols-2 lg:grid-cols-3"
      : "grid gap-x-4 gap-y-2 sm:grid-cols-2";

  return (
    <dl className={gridClass}>
      {fields.map((field, index) =>
        field.inline ? (
          <div key={index} className="flex items-baseline gap-2">
            <dt className="text-sm text-muted-foreground whitespace-nowrap">{field.label}:</dt>
            <dd className="text-sm font-medium">{field.value || "—"}</dd>
          </div>
        ) : (
          <div key={index}>
            <dt className="text-xs text-muted-foreground">{field.label}</dt>
            <dd className="text-sm font-medium">{field.value || "—"}</dd>
          </div>
        )
      )}
    </dl>
  );
}
