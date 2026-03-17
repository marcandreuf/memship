"use client";

import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { useChangeMemberStatus } from "../hooks/use-members";
import type { MemberData } from "../services/members-api";

const STATUS_ACTIONS: Record<string, string[]> = {
  pending: ["active", "cancelled"],
  active: ["suspended", "cancelled"],
  suspended: ["active", "cancelled"],
  expired: ["active"],
  cancelled: [],
};

const ACTION_VARIANTS: Record<string, "default" | "destructive" | "outline"> = {
  active: "default",
  suspended: "destructive",
  cancelled: "destructive",
};

interface MemberStatusActionsProps {
  member: MemberData;
}

export function MemberStatusActions({ member }: MemberStatusActionsProps) {
  const t = useTranslations();
  const { mutateAsync: changeStatus, isPending } = useChangeMemberStatus();

  const actions = STATUS_ACTIONS[member.status] || [];

  if (actions.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {actions.map((status) => (
        <Button
          key={status}
          variant={ACTION_VARIANTS[status] || "outline"}
          size="sm"
          disabled={isPending}
          onClick={() => changeStatus({ id: member.id, status })}
        >
          {t(`members.action_${status}`)}
        </Button>
      ))}
    </div>
  );
}
