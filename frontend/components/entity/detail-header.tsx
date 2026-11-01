"use client";

import { type ReactNode } from "react";
import { Badge, type badgeVariants } from "@/components/ui/badge";
import { Breadcrumbs } from "./breadcrumbs";
import { useReturnTo } from "@/hooks/use-return-to";
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
  // A record has several parents, so the first crumb each page hardcodes names
  // whichever one its module happens to sit under. When the URL says where the
  // page was opened from, that is the true parent and it replaces the static
  // one, which also makes the breadcrumb the way back (memship#471).
  //
  // Only the first crumb is replaced: the rest, ending in this record, still
  // describe the page. A page passing a single crumb has no module crumb to
  // swap, so the return is prepended instead of overwriting the record.
  const returnTo = useReturnTo();
  const items = returnTo
    ? [returnTo, ...breadcrumbs.slice(breadcrumbs.length > 1 ? 1 : 0)]
    : breadcrumbs;

  return (
    <div className="space-y-1">
      <Breadcrumbs items={items} />
      {/* The actions wrap below the title rather than squeezing it. They were
          `shrink-0` beside a `truncate` heading on a row that could not wrap,
          so at a narrow desktop width the receipt number rendered as "F.."
          while the buttons kept their full width (#398). */}
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 min-w-0 sm:min-w-[16rem] sm:flex-1">
          <h1 className="text-2xl font-bold truncate">{title}</h1>
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
