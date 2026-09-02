"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Link, useRouter } from "@/lib/i18n/routing";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PageInfo } from "@/components/page-info";
import { SearchInput } from "@/components/entity/search-input";
import { TableSkeleton } from "@/components/ui/skeletons";
import { useSearchParam, useStatusParam } from "@/hooks/use-url-state";
import { useSpaces } from "@/features/bookings/hooks/use-bookings";
import { SpaceForm } from "@/features/bookings/components/space-form";
import { usePermissions } from "@/features/auth/hooks/use-permissions";

export default function SpacesPage() {
  const t = useTranslations();
  const { has } = usePermissions();
  const canWrite = has("bookings.write");
  const router = useRouter();
  const { data: spaces, isLoading } = useSpaces();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useSearchParam();
  const [statusFilter, setStatusFilter] = useStatusParam();

  // The spaces endpoint returns every row unpaginated, so search and the
  // active filter run client-side — the same arrangement Groups uses.
  const filteredSpaces = spaces?.filter((space) => {
    if (statusFilter === "active" && !space.is_active) return false;
    if (statusFilter === "inactive" && space.is_active) return false;
    if (!search) return true;
    const term = search.toLowerCase();
    return (
      space.name.toLowerCase().includes(term) ||
      (space.space_type?.toLowerCase().includes(term) ?? false) ||
      (space.description?.toLowerCase().includes(term) ?? false)
    );
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold">{t("bookings.spaces.title")}</h1>
          <PageInfo text={t("bookings.spaces.info")} />
        </div>
        {canWrite && (
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button size="sm">{t("bookings.spaces.create")}</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{t("bookings.spaces.create")}</DialogTitle>
              </DialogHeader>
              <SpaceForm space={null} onSuccess={() => setOpen(false)} />
            </DialogContent>
          </Dialog>
        )}
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder={t("common.search")}
          className="sm:max-w-xs"
        />
        <Select
          value={statusFilter}
          onValueChange={(v) => setStatusFilter(v === "all" ? "" : v)}
        >
          <SelectTrigger className="sm:w-48">
            <SelectValue placeholder={t("bookings.spaces.allStatuses")} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("bookings.spaces.allStatuses")}</SelectItem>
            <SelectItem value="active">{t("bookings.spaces.active")}</SelectItem>
            <SelectItem value="inactive">{t("bookings.spaces.inactive")}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <TableSkeleton rows={4} columns={4} />
      ) : !filteredSpaces?.length ? (
        <div className="py-8 text-center text-muted-foreground">
          {t("bookings.spaces.noSpaces")}
        </div>
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden md:block rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("bookings.spaces.name")}</TableHead>
                  <TableHead>{t("bookings.spaces.type")}</TableHead>
                  <TableHead>{t("bookings.spaces.hours")}</TableHead>
                  <TableHead>{t("bookings.spaces.status")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredSpaces.map((space) => (
                  <TableRow
                    key={space.id}
                    className="cursor-pointer"
                    onClick={() => router.push(`/spaces/${space.id}`)}
                  >
                    <TableCell className="font-medium">{space.name}</TableCell>
                    <TableCell>{space.space_type ?? "—"}</TableCell>
                    <TableCell>
                      {space.open_time.slice(0, 5)}–{space.close_time.slice(0, 5)}
                    </TableCell>
                    <TableCell>
                      <Badge variant={space.is_active ? "default" : "secondary"}>
                        {space.is_active
                          ? t("bookings.spaces.active")
                          : t("bookings.spaces.inactive")}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Mobile card view */}
          <div className="space-y-3 md:hidden">
            {filteredSpaces.map((space) => (
              <Link
                key={space.id}
                href={`/spaces/${space.id}`}
                className="block rounded-lg border p-4 hover:bg-accent transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-medium">{space.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {space.open_time.slice(0, 5)}–{space.close_time.slice(0, 5)}
                      {space.space_type ? ` · ${space.space_type}` : ""}
                    </p>
                  </div>
                  <Badge variant={space.is_active ? "default" : "secondary"}>
                    {space.is_active
                      ? t("bookings.spaces.active")
                      : t("bookings.spaces.inactive")}
                  </Badge>
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
