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
import { useMembers } from "../hooks/use-members";

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  active: "default",
  pending: "secondary",
  suspended: "destructive",
  cancelled: "outline",
  expired: "outline",
};

export function MemberList() {
  const t = useTranslations();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");

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
          <Button>{t("members.createMember")}</Button>
        </Link>
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
        <div className="py-8 text-center text-muted-foreground">
          {t("common.loading")}
        </div>
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
                  <TableHead>{t("common.actions")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((member) => (
                  <TableRow key={member.id}>
                    <TableCell className="font-mono text-sm">
                      {member.member_number}
                    </TableCell>
                    <TableCell>
                      {member.person.first_name} {member.person.last_name}
                    </TableCell>
                    <TableCell>{member.person.email || "—"}</TableCell>
                    <TableCell>{member.membership_type_name || "—"}</TableCell>
                    <TableCell>
                      <Badge variant={STATUS_VARIANTS[member.status] || "outline"}>
                        {t(`status.${member.status}`)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Link href={`/members/${member.id}`}>
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
                  <Badge variant={STATUS_VARIANTS[member.status] || "outline"}>
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
          {data.meta.total_pages > 1 && (
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                {t("members.showing", {
                  from: (data.meta.page - 1) * data.meta.per_page + 1,
                  to: Math.min(data.meta.page * data.meta.per_page, data.meta.total),
                  total: data.meta.total,
                })}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                >
                  {t("members.previous")}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= data.meta.total_pages}
                  onClick={() => setPage(page + 1)}
                >
                  {t("members.next")}
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
