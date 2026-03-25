"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { toast } from "sonner";
import { Pagination } from "@/components/entity/pagination";
import {
  useActivityRegistrations,
  useChangeRegistrationStatus,
} from "../hooks/use-registrations";
import { TabContentSkeleton } from "@/components/ui/skeletons";
import type { RegistrationData } from "../services/registrations-api";

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  confirmed: "default",
  waitlist: "secondary",
  cancelled: "destructive",
  pending: "outline",
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface RegistrationsTabProps {
  activityId: number;
}

export function RegistrationsTab({ activityId }: RegistrationsTabProps) {
  const t = useTranslations();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const { data, isLoading } = useActivityRegistrations({
    activityId,
    page,
    per_page: 20,
    status: statusFilter || undefined,
  });

  if (isLoading) {
    return <TabContentSkeleton />;
  }

  return (
    <div className="space-y-3 table-compact">
      <div className="flex items-center gap-3">
        <Select
          value={statusFilter}
          onValueChange={(v) => {
            setStatusFilter(v === "all" ? "" : v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-40">
            <SelectValue placeholder={t("common.filter")} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("activities.allStatuses")}</SelectItem>
            <SelectItem value="confirmed">{t("activities.registration.status.confirmed")}</SelectItem>
            <SelectItem value="waitlist">{t("activities.registration.status.waitlist")}</SelectItem>
            <SelectItem value="cancelled">{t("activities.registration.status.cancelled")}</SelectItem>
            <SelectItem value="pending">{t("activities.registration.status.pending")}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {!data?.items.length ? (
        <p className="py-4 text-sm text-muted-foreground">{t("activities.registration.noRegistrations")}</p>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("activities.registration.member")}</TableHead>
                <TableHead>{t("common.status")}</TableHead>
                <TableHead>{t("activities.registration.date")}</TableHead>
                <TableHead>{t("common.actions")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((reg) => (
                <RegistrationRow key={reg.id} registration={reg} />
              ))}
            </TableBody>
          </Table>

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

function RegistrationRow({ registration }: { registration: RegistrationData }) {
  const t = useTranslations();
  const changeMutation = useChangeRegistrationStatus();
  const memberName = registration.member
    ? `${registration.member.first_name} ${registration.member.last_name}`
    : `Member #${registration.member_id}`;

  async function handleStatusChange(newStatus: string) {
    try {
      await changeMutation.mutateAsync({ id: registration.id, status: newStatus });
      toast.success(t("toast.success.updated"));
    } catch { /* global handler shows error toast */ }
  }

  return (
    <TableRow>
      <TableCell>
        <div>
          <span className="font-medium">{memberName}</span>
          {registration.member?.member_number && (
            <span className="ml-2 text-xs text-muted-foreground font-mono">
              {registration.member.member_number}
            </span>
          )}
        </div>
      </TableCell>
      <TableCell>
        <Badge variant={STATUS_VARIANTS[registration.status] || "outline"}>
          {t(`activities.registration.status.${registration.status}`)}
        </Badge>
      </TableCell>
      <TableCell className="text-sm">{formatDate(registration.created_at)}</TableCell>
      <TableCell>
        {registration.status !== "cancelled" && (
          <Select
            value=""
            onValueChange={handleStatusChange}
          >
            <SelectTrigger className="w-32 h-8 text-xs">
              <SelectValue placeholder={t("activities.registration.changeStatus")} />
            </SelectTrigger>
            <SelectContent>
              {registration.status !== "confirmed" && (
                <SelectItem value="confirmed">{t("activities.registration.status.confirmed")}</SelectItem>
              )}
              {registration.status !== "waitlist" && (
                <SelectItem value="waitlist">{t("activities.registration.status.waitlist")}</SelectItem>
              )}
              <SelectItem value="cancelled">{t("activities.registration.status.cancelled")}</SelectItem>
            </SelectContent>
          </Select>
        )}
      </TableCell>
    </TableRow>
  );
}
