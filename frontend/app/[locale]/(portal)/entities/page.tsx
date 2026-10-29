"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import { Link, useRouter } from "@/lib/i18n/routing";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { SearchInput } from "@/components/entity/search-input";
import { PageInfo } from "@/components/page-info";
import { Pagination } from "@/components/entity/pagination";
import { TableSkeleton } from "@/components/ui/skeletons";
import { useEntities, useEntityKinds } from "@/features/entities/hooks/use-entities";
import { useSearchParam, usePageParam, useStatusParam } from "@/hooks/use-url-state";
import { usePermissions } from "@/features/auth/hooks/use-permissions";

export default function EntitiesPage() {
  const t = useTranslations();
  const { has } = usePermissions();
  const canWrite = has("entities.write");
  const router = useRouter();
  const [page, setPage] = usePageParam();
  const [search, setSearch] = useSearchParam();
  const [kindFilter, setKindFilter] = useStatusParam();
  const { data: kinds = [] } = useEntityKinds();

  const params = useMemo(() => {
    const p = new URLSearchParams();
    p.set("page", String(page));
    p.set("per_page", "20");
    if (search) p.set("search", search);
    if (kindFilter) p.set("kind", kindFilter);
    return p;
  }, [page, search, kindFilter]);

  const { data, isLoading } = useEntities(params);

  if (isLoading) return <TableSkeleton />;

  const items = data?.items || [];
  const meta = data?.meta || { page: 1, per_page: 20, total: 0, total_pages: 1 };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold">{t("entities.title")}</h1>
          <PageInfo text={t("entities.info")} />
        </div>
        {canWrite && (
          <Button onClick={() => router.push("/entities/new")}>
            {t("entities.newEntity")}
          </Button>
        )}
      </div>

      <div className="flex items-center gap-3">
        <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder={t("common.search")} />
        <Select value={kindFilter} onValueChange={(v) => { setKindFilter(v === "all" ? "" : v); setPage(1); }}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder={t("entities.kind")} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("common.all")}</SelectItem>
            {kinds.map((k) => (
              <SelectItem key={k.code} value={k.code}>
                {t(`entities.kinds.${k.code}`)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {items.length === 0 ? (
        <div className="py-8 text-center text-muted-foreground">{t("entities.noEntities")}</div>
      ) : (
        <>
        <div className="hidden @3xl:block rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("entities.name")}</TableHead>
              <TableHead>{t("entities.kind")}</TableHead>
              <TableHead>{t("entities.nationalId")}</TableHead>
              <TableHead>{t("auth.email")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((e) => (
              <TableRow
                key={e.id}
                className="cursor-pointer hover:bg-muted/50"
                onClick={() => router.push(`/entities/${e.id}`)}
              >
                <TableCell className="font-medium">{e.name}</TableCell>
                <TableCell>
                  <Badge variant="outline">{t(`entities.kinds.${e.kind}`)}</Badge>
                </TableCell>
                <TableCell className="font-mono text-sm">{e.national_id || "—"}</TableCell>
                <TableCell className="text-sm">{e.email || "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        </div>

        <div className="space-y-3 @3xl:hidden">
          {items.map((e) => (
            <Link
              key={e.id}
              href={`/entities/${e.id}`}
              className="block rounded-lg border p-4 hover:bg-accent transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <p className="truncate font-medium">{e.name}</p>
                <Badge variant="outline">{t(`entities.kinds.${e.kind}`)}</Badge>
              </div>
              <div className="mt-1 flex items-center justify-between gap-2">
                <span className="truncate text-sm text-muted-foreground">{e.email || "—"}</span>
                <span className="shrink-0 font-mono text-sm text-muted-foreground">
                  {e.national_id || ""}
                </span>
              </div>
            </Link>
          ))}
        </div>
        </>
      )}

      <Pagination
        page={meta.page}
        totalPages={meta.total_pages}
        total={meta.total}
        perPage={meta.per_page}
        onPageChange={(p) => setPage(p)}
      />
    </div>
  );
}
