"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "@/lib/i18n/routing";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { MEMBER_STATUS_VARIANTS } from "@/lib/status-variants";
import { useMembers } from "@/features/members/hooks/use-members";

interface MembersTabProps {
  groupId: number;
}

export function MembersTab({ groupId }: MembersTabProps) {
  const t = useTranslations();
  const router = useRouter();
  const { data, isLoading } = useMembers({ group_id: groupId });

  if (isLoading) {
    return <div className="py-4 text-center text-muted-foreground">{t("common.loading")}</div>;
  }

  const members = data?.items || [];

  if (!members.length) {
    return <p className="py-4 text-sm text-muted-foreground">{t("groups.noMembers")}</p>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t("members.memberNumber")}</TableHead>
          <TableHead>{t("members.name")}</TableHead>
          <TableHead>{t("auth.email")}</TableHead>
          <TableHead>{t("common.status")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {members.map((member) => (
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
            <TableCell>
              <Badge variant={MEMBER_STATUS_VARIANTS[member.status] || "outline"}>
                {t(`status.${member.status}`)}
              </Badge>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
