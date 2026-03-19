"use client";

import { type ReactNode } from "react";
import { Badge, type badgeVariants } from "@/components/ui/badge";
import { Breadcrumbs } from "./breadcrumbs";
import type { VariantProps } from "class-variance-authority";

interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface DetailHeaderProps {
  breadcrumbs: BreadcrumbItem[];
  title: string;
  badge?: {
    label: string;
    variant?: VariantProps<typeof badgeVariants>["variant"];
  };
  actions?: ReactNode;
}

export function DetailHeader({
  breadcrumbs,
  title,
  badge,
  actions,
}: DetailHeaderProps) {
  return (
    <div className="space-y-1">
      <Breadcrumbs items={breadcrumbs} />
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <h1 className="text-lg font-bold truncate">{title}</h1>
          {badge && (
            <Badge variant={badge.variant || "default"}>{badge.label}</Badge>
          )}
        </div>
        {actions && (
          <div className="flex flex-wrap gap-2 shrink-0">{actions}</div>
        )}
      </div>
    </div>
  );
}
