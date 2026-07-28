"use client";

import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useChangeMemberStatus } from "../hooks/use-members";
import { RegistrationReviewActions } from "./registration-review-actions";
import type { MemberData } from "../services/members-api";

// `pending` is intentionally absent: a pending member is an unreviewed
// registration, handled by RegistrationReviewActions below so that approving
// also allocates the member number.
const STATUS_ACTIONS: Record<string, string[]> = {
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

  if (member.status === "pending") {
    return <RegistrationReviewActions member={member} />;
  }

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
          onClick={async () => {
            try {
              await changeStatus({ id: member.id, status });
              toast.success(t("toast.success.updated"));
            } catch { /* global handler shows error toast */ }
          }}
        >
          {t(`members.action_${status}`)}
        </Button>
      ))}
    </div>
  );
}
