"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/lib/i18n/routing";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PageInfo } from "@/components/page-info";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { useActivities } from "@/features/activities/hooks/use-activities";

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  draft: "outline",
  published: "default",
  archived: "secondary",
  cancelled: "destructive",
  completed: "secondary",
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function ActivitiesPage() {
  const t = useTranslations();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin" || user?.role === "super_admin";

  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");

  const { data, isLoading } = useActivities({
    page,
    per_page: 20,
    search: search || undefined,
    status: isAdmin ? statusFilter || undefined : "published",
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold">{t("activities.title")}</h1>
          <PageInfo text={t("activities.info")} />
        </div>
        {isAdmin && (
          <Link href="/activities/new">
            <Button>{t("activities.createActivity")}</Button>
          </Link>
        )}
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <Input
          placeholder={t("common.search")}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="sm:max-w-xs"
        />
        {isAdmin && (
          <Select
            value={statusFilter}
            onValueChange={(v) => {
              setStatusFilter(v === "all" ? "" : v);
              setPage(1);
            }}
          >
            <SelectTrigger className="sm:w-48">
              <SelectValue placeholder={t("activities.allStatuses")} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("activities.allStatuses")}</SelectItem>
              <SelectItem value="draft">{t("activities.status.draft")}</SelectItem>
              <SelectItem value="published">{t("activities.status.published")}</SelectItem>
              <SelectItem value="archived">{t("activities.status.archived")}</SelectItem>
              <SelectItem value="cancelled">{t("activities.status.cancelled")}</SelectItem>
            </SelectContent>
          </Select>
        )}
      </div>

      {isLoading ? (
        <div className="py-8 text-center text-muted-foreground">
          {t("common.loading")}
        </div>
      ) : !data?.items.length ? (
        <div className="py-8 text-center text-muted-foreground">
          {t("activities.noActivities")}
        </div>
      ) : isAdmin ? (
        <>
          {/* Admin: Desktop table */}
          <div className="hidden md:block rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("activities.name")}</TableHead>
                  <TableHead>{t("activities.startsAt")}</TableHead>
                  <TableHead>{t("activities.location")}</TableHead>
                  <TableHead>{t("activities.capacity")}</TableHead>
                  <TableHead>{t("common.status")}</TableHead>
                  <TableHead>{t("common.actions")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((activity) => (
                  <TableRow key={activity.id}>
                    <TableCell className="font-medium">{activity.name}</TableCell>
                    <TableCell>{formatDate(activity.starts_at)}</TableCell>
                    <TableCell>{activity.location || "—"}</TableCell>
                    <TableCell>
                      {activity.current_participants}/{activity.max_participants}
                    </TableCell>
                    <TableCell>
                      <Badge variant={STATUS_VARIANTS[activity.status] || "outline"}>
                        {t(`activities.status.${activity.status}`)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Link href={`/activities/${activity.id}`}>
                        <Button variant="outline" size="sm">
                          {t("common.edit")}
                        </Button>
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Admin: Mobile card view */}
          <div className="space-y-3 md:hidden">
            {data.items.map((activity) => (
              <Link
                key={activity.id}
                href={`/activities/${activity.id}`}
                className="block rounded-lg border p-4 hover:bg-accent transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium">{activity.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {formatDate(activity.starts_at)}
                    </p>
                  </div>
                  <Badge variant={STATUS_VARIANTS[activity.status] || "outline"}>
                    {t(`activities.status.${activity.status}`)}
                  </Badge>
                </div>
                {activity.location && (
                  <p className="mt-1 text-sm text-muted-foreground">
                    {activity.location}
                  </p>
                )}
                <p className="mt-1 text-sm text-muted-foreground">
                  {activity.current_participants}/{activity.max_participants}
                </p>
              </Link>
            ))}
          </div>
        </>
      ) : (
        /* Member: Card view for published activities */
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((activity) => (
            <Link
              key={activity.id}
              href={`/activities/${activity.id}`}
              className="block rounded-lg border p-4 hover:bg-accent transition-colors"
            >
              <h3 className="font-medium">{activity.name}</h3>
              {activity.short_description && (
                <p className="mt-1 text-sm text-muted-foreground line-clamp-2">
                  {activity.short_description}
                </p>
              )}
              <div className="mt-3 space-y-1 text-sm text-muted-foreground">
                <p>{formatDate(activity.starts_at)} — {formatDate(activity.ends_at)}</p>
                {activity.location && <p>{activity.location}</p>}
                <p>
                  {activity.available_spots > 0
                    ? t("activities.availableSpots", { count: activity.available_spots })
                    : t("activities.full")}
                </p>
              </div>
              {activity.is_registration_open && (
                <Badge className="mt-2" variant="default">
                  {t("activities.status.published")}
                </Badge>
              )}
            </Link>
          ))}
        </div>
      )}

      {/* Pagination */}
      {data && data.meta.total_pages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            {t("common.back")}
          </Button>
          <span className="text-sm text-muted-foreground">
            {page} / {data.meta.total_pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= data.meta.total_pages}
            onClick={() => setPage(page + 1)}
          >
            &rarr;
          </Button>
        </div>
      )}
    </div>
  );
}
