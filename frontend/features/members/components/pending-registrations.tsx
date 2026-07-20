"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/lib/i18n/routing";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Pagination } from "@/components/entity/pagination";
import { TableSkeleton } from "@/components/ui/skeletons";
import { usePageParam } from "@/hooks/use-url-state";
import { useMembers } from "../hooks/use-members";
import { RegistrationReviewActions } from "./registration-review-actions";

/** Admin queue of self-registrations waiting for a decision. */
export function PendingRegistrations() {
  const t = useTranslations();
  const [page, setPage] = usePageParam();

  const { data, isLoading } = useMembers({
    page,
    per_page: 20,
    status: "pending",
  });

  const items = data?.items ?? [];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">{t("members.registration.queueTitle")}</h1>
        <p className="text-sm text-muted-foreground">
          {t("members.registration.queueDescription")}
        </p>
      </div>

      {isLoading ? (
        <TableSkeleton />
      ) : items.length === 0 ? (
        <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
          {t("members.registration.queueEmpty")}
        </div>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("members.name")}</TableHead>
                <TableHead>{t("auth.email")}</TableHead>
                <TableHead>{t("members.membershipType")}</TableHead>
                <TableHead className="text-right">
                  {t("common.actions")}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((member) => (
                <TableRow key={member.id}>
                  <TableCell>
                    <Link
                      href={`/members/${member.id}`}
                      className="font-medium text-primary underline-offset-4 hover:underline"
                    >
                      {member.person.first_name} {member.person.last_name}
                    </Link>
                  </TableCell>
                  <TableCell>{member.person.email ?? "—"}</TableCell>
                  <TableCell>{member.membership_type_name ?? "—"}</TableCell>
                  <TableCell>
                    <div className="flex justify-end">
                      <RegistrationReviewActions member={member} />
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

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