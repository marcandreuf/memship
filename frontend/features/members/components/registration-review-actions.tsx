"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useApproveMember, useRejectMember } from "../hooks/use-members";
import type { MemberData } from "../services/members-api";

interface RegistrationReviewActionsProps {
  member: MemberData;
  size?: "sm" | "default";
}

/**
 * Approve / reject actions for a pending self-registration.
 *
 * These deliberately do not reuse the generic status-change action: approving
 * also allocates the member number and notifies the applicant, which only the
 * dedicated endpoints do.
 */
export function RegistrationReviewActions({
  member,
  size = "sm",
}: RegistrationReviewActionsProps) {
  const t = useTranslations();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [reason, setReason] = useState("");

  const { mutateAsync: approve, isPending: isApproving } = useApproveMember();
  const { mutateAsync: reject, isPending: isRejecting } = useRejectMember();

  const busy = isApproving || isRejecting;

  async function handleApprove() {
    try {
      await approve(member.id);
      toast.success(t("members.registration.approved"));
    } catch {
      /* global handler shows the error toast */
    }
  }

  async function handleReject() {
    try {
      await reject({ id: member.id, reason: reason.trim() || undefined });
      setRejectOpen(false);
      setReason("");
      toast.success(t("members.registration.rejected"));
    } catch {
      /* global handler shows the error toast */
    }
  }

  return (
    <>
      <div className="flex flex-wrap gap-2">
        <Button size={size} disabled={busy} onClick={() => setConfirmOpen(true)}>
          {t("members.registration.approve")}
        </Button>
        <Button
          size={size}
          variant="destructive"
          disabled={busy}
          onClick={() => setRejectOpen(true)}
        >
          {t("members.registration.reject")}
        </Button>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={t("members.registration.approveTitle")}
        description={t("members.registration.approveDescription")}
        confirmLabel={t("members.registration.approve")}
        cancelLabel={t("common.cancel")}
        variant="default"
        onConfirm={handleApprove}
      />

      <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("members.registration.rejectTitle")}</DialogTitle>
            <DialogDescription>
              {t("members.registration.rejectDescription")}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <Label htmlFor="reject-reason">
              {t("members.registration.reasonLabel")}
            </Label>
            <Textarea
              id="reject-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={t("members.registration.reasonPlaceholder")}
              maxLength={2000}
              rows={3}
            />
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setRejectOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              variant="destructive"
              disabled={isRejecting}
              onClick={handleReject}
            >
              {t("members.registration.reject")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}