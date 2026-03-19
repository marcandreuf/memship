"use client";

import { ChevronRight } from "lucide-react";
import { Link } from "@/lib/i18n/routing";

interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface BreadcrumbsProps {
  items: BreadcrumbItem[];
}

export function Breadcrumbs({ items }: BreadcrumbsProps) {
  return (
    <nav className="flex items-center gap-1 text-sm text-muted-foreground overflow-hidden">
      {items.map((item, index) => {
        const isLast = index === items.length - 1;
        return (
          <span key={index} className="flex items-center gap-1 min-w-0">
            {index > 0 && <ChevronRight className="h-3.5 w-3.5 shrink-0" />}
            {isLast || !item.href ? (
              <span
                className={`truncate ${isLast ? "font-medium text-foreground" : ""}`}
              >
                {item.label}
              </span>
            ) : (
              <Link
                href={item.href}
                className="truncate hover:text-foreground transition-colors"
              >
                {item.label}
              </Link>
            )}
          </span>
        );
      })}
    </nav>
  );
}
