"use client";

import { useTranslations } from "next-intl";
import { Link, useRouter } from "@/lib/i18n/routing";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TableSkeleton } from "@/components/ui/skeletons";
import { PageInfo } from "@/components/page-info";
import { Pagination } from "@/components/entity/pagination";
import { usePageParam } from "@/hooks/use-url-state";
import { useFormatters } from "@/hooks/use-formatters";
import { MEMBER_STATUS_VARIANTS } from "@/lib/status-variants";
import { usePaidTierWithoutPurchase } from "../hooks/use-paid-tier-without-purchase";

/**
 * Members the old sign-up path parked on a priced tier nobody bought. Read-only
 * on purpose: the report cannot tell an accident from a decision, so each row
 * is a prompt to open the member and choose, not something to fix in bulk.
 */
export function PaidTierWithoutPurchase() {
  const t = useTranslations();
  const router = useRouter();
  const { formatCurrency, formatDate } = useFormatters();
  const [page, setPage] = usePageParam();
  const { data, isLoading } = usePaidTierWithoutPurchase(page);

  const items = data?.items ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h1 className="text-2xl font-bold">
          {t("reports.paidTierWithoutPurchase.title")}
        </h1>
        <PageInfo text={t("reports.paidTierWithoutPurchase.info")} />
      </div>
      <p className="text-sm text-muted-foreground">
        {t("reports.paidTierWithoutPurchase.description")}
      </p>

      {isLoading ? (
        <TableSkeleton />
      ) : items.length === 0 ? (
        <div className="py-8 text-center text-muted-foreground">
          {t("reports.paidTierWithoutPurchase.empty")}
        </div>
      ) : (
        <>
          <div className="hidden @3xl:block rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("members.name")}</TableHead>
                  <TableHead>{t("members.memberNumber")}</TableHead>
                  <TableHead>{t("common.status")}</TableHead>
                  <TableHead>{t("members.membershipType")}</TableHead>
                  <TableHead className="text-right">
                    {t("members.typePrice")}
                  </TableHead>
                  <TableHead className="text-right">
                    {t("reports.paidTierWithoutPurchase.unpaidReceipts")}
                  </TableHead>
                  <TableHead className="text-right">
                    {t("reports.paidTierWithoutPurchase.unpaidAmount")}
                  </TableHead>
                  <TableHead>{t("members.joinedAt")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((row) => (
                  <TableRow
                    key={row.member_id}
                    className="cursor-pointer"
                    onClick={() => router.push(`/members/${row.member_id}`)}
                  >
                    <TableCell className="font-medium">{row.full_name}</TableCell>
                    <TableCell>{row.member_number ?? "—"}</TableCell>
                    <TableCell>
                      <Badge variant={MEMBER_STATUS_VARIANTS[row.status] ?? "outline"}>
                        {t(`status.${row.status}`)}
                      </Badge>
                    </TableCell>
                    <TableCell>{row.membership_type_name}</TableCell>
                    <TableCell className="text-right">
                      {formatCurrency(row.base_price)}
                    </TableCell>
                    <TableCell className="text-right">
                      {row.unpaid_receipts}
                    </TableCell>
                    <TableCell className="text-right">
                      {formatCurrency(row.unpaid_amount)}
                    </TableCell>
                    <TableCell>{formatDate(row.joined_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <div className="space-y-3 @3xl:hidden">
            {items.map((row) => (
              <Link
                key={row.member_id}
                href={`/members/${row.member_id}`}
                className="block rounded-md border p-3"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{row.full_name}</span>
                  <Badge variant={MEMBER_STATUS_VARIANTS[row.status] ?? "outline"}>
                    {t(`status.${row.status}`)}
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  {row.membership_type_name} · {formatCurrency(row.base_price)}
                </p>
                <p className="text-sm text-muted-foreground">
                  {t("reports.paidTierWithoutPurchase.unpaidAmount")}:{" "}
                  {formatCurrency(row.unpaid_amount)} ({row.unpaid_receipts})
                </p>
              </Link>
            ))}
          </div>

          {data && (
            <Pagination
              page={page}
              totalPages={data.meta.total_pages}
              total={data.meta.total}
              perPage={data.meta.per_page}
              onPageChange={setPage}
            />
          )}
        </>
      )}
    </div>
  );
}
