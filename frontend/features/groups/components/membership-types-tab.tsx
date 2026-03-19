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
import { useMembershipTypes } from "@/features/members/hooks/use-members";

interface MembershipTypesTabProps {
  groupId: number;
}

export function MembershipTypesTab({ groupId }: MembershipTypesTabProps) {
  const t = useTranslations();
  const router = useRouter();
  const { data: allTypes, isLoading } = useMembershipTypes();

  const types = allTypes?.filter((mt) => mt.group_id === groupId) || [];

  if (isLoading) {
    return <div className="py-4 text-center text-muted-foreground">{t("common.loading")}</div>;
  }

  if (!types.length) {
    return <p className="py-4 text-sm text-muted-foreground">{t("groups.noMembershipTypes")}</p>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t("members.typeName")}</TableHead>
          <TableHead>{t("members.typeSlug")}</TableHead>
          <TableHead>{t("members.typePrice")}</TableHead>
          <TableHead>{t("members.typeBilling")}</TableHead>
          <TableHead>{t("common.status")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {types.map((mt) => (
          <TableRow
            key={mt.id}
            className="cursor-pointer"
            onClick={() => router.push("/settings")}
          >
            <TableCell className="font-medium">{mt.name}</TableCell>
            <TableCell className="font-mono text-sm">{mt.slug}</TableCell>
            <TableCell>{Number(mt.base_price).toFixed(2)} EUR</TableCell>
            <TableCell>{mt.billing_frequency}</TableCell>
            <TableCell>
              <Badge variant={mt.is_active ? "default" : "outline"}>
                {mt.is_active ? t("status.active") : t("members.inactive")}
              </Badge>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
