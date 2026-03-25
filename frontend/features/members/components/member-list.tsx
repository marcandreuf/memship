"use client";

import { useTranslations } from "next-intl";
import { Link, useRouter } from "@/lib/i18n/routing";
import { Button } from "@/components/ui/button";
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
import { SearchInput } from "@/components/entity/search-input";
import { Pagination } from "@/components/entity/pagination";
import { MEMBER_STATUS_VARIANTS } from "@/lib/status-variants";
import { TableSkeleton } from "@/components/ui/skeletons";
import { useSearchParam, usePageParam, useStatusParam } from "@/hooks/use-url-state";
import { useMembers } from "../hooks/use-members";

export function MemberList() {
  const t = useTranslations();
  const router = useRouter();
  const [page, setPage] = usePageParam();
  const [search, setSearch] = useSearchParam();
  const [statusFilter, setStatusFilter] = useStatusParam();

  const { data, isLoading } = useMembers({
    page,
    per_page: 20,
    search: search || undefined,
    status: statusFilter || undefined,
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-bold">{t("nav.members")}</h1>
        <Link href="/members/new">
          <Button size="sm">{t("members.createMember")}</Button>
        </Link>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <SearchInput
          value={search}
          onChange={(v) => {
            setSearch(v);
            setPage(1);
          }}
          placeholder={t("common.search")}
          className="sm:max-w-xs"
        />
        <Select
          value={statusFilter}
          onValueChange={(v) => {
            setStatusFilter(v === "all" ? "" : v);
            setPage(1);
          }}
        >
          <SelectTrigger className="sm:w-40">
            <SelectValue placeholder={t("common.filter")} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("members.allStatuses")}</SelectItem>
            <SelectItem value="active">{t("status.active")}</SelectItem>
            <SelectItem value="pending">{t("status.pending")}</SelectItem>
            <SelectItem value="suspended">{t("status.suspended")}</SelectItem>
            <SelectItem value="cancelled">{t("status.cancelled")}</SelectItem>
            <SelectItem value="expired">{t("status.expired")}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <TableSkeleton rows={8} columns={5} />
      ) : !data?.items.length ? (
        <div className="py-8 text-center text-muted-foreground">
          {t("common.noResults")}
        </div>
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden md:block rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("members.memberNumber")}</TableHead>
                  <TableHead>{t("members.name")}</TableHead>
                  <TableHead>{t("auth.email")}</TableHead>
                  <TableHead>{t("members.membershipType")}</TableHead>
                  <TableHead>{t("common.status")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((member) => (
                  <TableRow
                    key={member.id}
                    className="cursor-pointer"
                    onClick={() => router.push(`/members/${member.id}`)}
                  >
                    <TableCell className="font-mono text-sm">
                      {member.member_number}
                    </TableCell>
                    <TableCell>
                      {member.person.first_name} {member.person.last_name}
                    </TableCell>
                    <TableCell>{member.person.email || "—"}</TableCell>
                    <TableCell>{member.membership_type_name || "—"}</TableCell>
                    <TableCell>
                      <Badge variant={MEMBER_STATUS_VARIANTS[member.status] || "outline"}>
                        {t(`status.${member.status}`)}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Mobile card view */}
          <div className="space-y-3 md:hidden">
            {data.items.map((member) => (
              <Link
                key={member.id}
                href={`/members/${member.id}`}
                className="block rounded-lg border p-4 hover:bg-accent transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium">
                      {member.person.first_name} {member.person.last_name}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {member.member_number}
                    </p>
                  </div>
                  <Badge variant={MEMBER_STATUS_VARIANTS[member.status] || "outline"}>
                    {t(`status.${member.status}`)}
                  </Badge>
                </div>
                {member.person.email && (
                  <p className="mt-1 text-sm text-muted-foreground">
                    {member.person.email}
                  </p>
                )}
              </Link>
            ))}
          </div>

          {/* Pagination */}
          <Pagination
            page={page}
            totalPages={data.meta.total_pages}
            total={data.meta.total}
            perPage={data.meta.per_page}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}
