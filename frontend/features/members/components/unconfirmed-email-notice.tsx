"use client";

import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useConfirmMemberEmail } from "../hooks/use-members";
import type { MemberData } from "../services/members-api";

interface UnconfirmedEmailNoticeProps {
  member: MemberData;
  /** `users.write` — confirming an address is an account action, not a member
   *  edit, so it is gated apart from the rest of the page. */
  canConfirm: boolean;
}

/**
 * Says why an active member cannot sign in, and offers the way out (#231).
 *
 * Sign-in is refused until the address is confirmed, and the only self-service
 * route to that is a link sent by email. When the club's mail is not working
 * the member is stuck and the admin sees nothing: an active member, no
 * indication that anything failed. This is that indication.
 *
 * Confirming here asserts the admin established the address some other way. It
 * is audit-logged as an admin confirmation rather than the member's own, which
 * is why the copy says whose word it rests on.
 */
export function UnconfirmedEmailNotice({
  member,
  canConfirm,
}: UnconfirmedEmailNoticeProps) {
  const t = useTranslations();
  const { mutateAsync: confirm, isPending } = useConfirmMemberEmail();

  if (member.email_verified !== false) return null;

  return (
    <Card className="border-amber-500/50 bg-amber-500/5 py-3">
      <CardContent className="flex flex-col gap-3 px-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-medium">
            {t("members.unconfirmedEmail.title")}
          </p>
          <p className="text-xs text-muted-foreground">
            {t("members.unconfirmedEmail.description")}
          </p>
        </div>
        {canConfirm && (
          <Button
            size="sm"
            variant="outline"
            disabled={isPending}
            onClick={async () => {
              try {
                await confirm(member.id);
                toast.success(t("members.unconfirmedEmail.confirmed"));
              } catch {
                /* global handler shows the error toast */
              }
            }}
          >
            {isPending
              ? t("common.loading")
              : t("members.unconfirmedEmail.action")}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
