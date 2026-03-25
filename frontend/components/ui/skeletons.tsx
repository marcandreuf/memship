import { Skeleton } from "@/components/ui/skeleton";

/**
 * Skeleton for table-based list pages (members, activities admin, groups).
 */
export function TableSkeleton({
  rows = 5,
  columns = 4,
}: {
  rows?: number;
  columns?: number;
}) {
  return (
    <div className="rounded-md border">
      <div className="border-b px-4 py-3 flex gap-4">
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={i} className="h-4 w-24" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex items-center gap-4 px-4 py-3 border-b last:border-0">
          {Array.from({ length: columns }).map((_, c) => (
            <Skeleton
              key={c}
              className={`h-4 ${c === 0 ? "w-16" : c === 1 ? "w-32" : "w-24"}`}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

/**
 * Skeleton for card grid views (activity cards, my-activities).
 */
export function CardGridSkeleton({ cards = 6 }: { cards?: number }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: cards }).map((_, i) => (
        <div key={i} className="flex rounded-lg border overflow-hidden">
          <div className="flex-1 p-4 space-y-3">
            <Skeleton className="h-5 w-3/4" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-6 w-16 rounded-full" />
          </div>
          <Skeleton className="w-28 shrink-0" />
        </div>
      ))}
    </div>
  );
}

/**
 * Skeleton for detail pages (member detail, activity detail, group detail).
 */
export function DetailSkeleton() {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-8 w-64" />
      </div>
      <div className="rounded-lg border p-6 space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="space-y-1.5">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-5 w-40" />
            </div>
          ))}
        </div>
      </div>
      <div className="flex gap-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-9 w-24 rounded-md" />
        ))}
      </div>
    </div>
  );
}

/**
 * Skeleton for form/settings pages.
 */
export function FormSkeleton({ fields = 4 }: { fields?: number }) {
  return (
    <div className="rounded-lg border p-6 space-y-6">
      {Array.from({ length: fields }).map((_, i) => (
        <div key={i} className="space-y-2">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-10 w-full rounded-md" />
        </div>
      ))}
      <Skeleton className="h-10 w-24 rounded-md" />
    </div>
  );
}

/**
 * Skeleton for tab content (compact, used inside tabs).
 */
export function TabContentSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3 py-2">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-16" />
        </div>
      ))}
    </div>
  );
}

/**
 * Full-page loading skeleton wrapper (centered, with padding).
 */
export function PageSkeleton({ children }: { children: React.ReactNode }) {
  return <div className="space-y-4">{children}</div>;
}
