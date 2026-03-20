"use client";

import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { Link } from "@/lib/i18n/routing";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { REGISTRATION_STATUS_VARIANTS } from "@/lib/status-variants";
import { useMemberRegistrations } from "../hooks/use-members";

interface MemberActivitiesTabProps {
  memberId: number;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function MemberActivitiesTab({ memberId }: MemberActivitiesTabProps) {
  const t = useTranslations();
  const { data, isLoading } = useMemberRegistrations(memberId);

  if (isLoading) return <p className="text-sm text-muted-foreground">{t("common.loading")}</p>;

  const registrations = data?.items || [];

  if (!registrations.length) {
    return <p className="text-sm text-muted-foreground">{t("members.noActivities")}</p>;
  }

  return (
    <div className="table-compact">
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t("activities.name")}</TableHead>
          <TableHead>{t("common.status")}</TableHead>
          <TableHead>{t("activities.startsAt")}</TableHead>
          <TableHead>{t("activities.location")}</TableHead>
          <TableHead>{t("members.registeredOn")}</TableHead>
          <TableHead>{t("members.amount")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {registrations.map((reg) => (
          <TableRow key={reg.id}>
            <TableCell className="font-medium">
              {reg.activity ? (
                <Link href={`/activities/${reg.activity_id}`} className="hover:underline">
                  {reg.activity.name}
                </Link>
              ) : (
                `Activity #${reg.activity_id}`
              )}
            </TableCell>
            <TableCell>
              <Badge variant={REGISTRATION_STATUS_VARIANTS[reg.status] || "outline"}>
                {t(`activities.registration.status.${reg.status}`)}
              </Badge>
            </TableCell>
            <TableCell>
              {reg.activity?.starts_at ? formatDate(reg.activity.starts_at) : "—"}
            </TableCell>
            <TableCell>
              {reg.activity?.location || "—"}
            </TableCell>
            <TableCell>{formatDate(reg.created_at)}</TableCell>
            <TableCell>
              {reg.discounted_amount != null
                ? `${Number(reg.discounted_amount).toFixed(2)} EUR`
                : reg.original_amount != null
                  ? `${Number(reg.original_amount).toFixed(2)} EUR`
                  : "—"}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
    </div>
  );
}
