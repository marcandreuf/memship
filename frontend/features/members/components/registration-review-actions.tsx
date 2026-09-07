"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  useApproveMember,
  useMembershipTypes,
  useRejectMember,
} from "../hooks/use-members";
import type { MemberData, MembershipTypeData } from "../services/members-api";

interface RegistrationReviewActionsProps {
  member: MemberData;
  size?: "sm" | "default";
}

function ageOn(dateOfBirth: string | null): number | null {
  if (!dateOfBirth) return null;
  const dob = new Date(dateOfBirth);
  if (Number.isNaN(dob.getTime())) return null;
  const today = new Date();
  let age = today.getFullYear() - dob.getFullYear();
  const beforeBirthday =
    today.getMonth() < dob.getMonth() ||
    (today.getMonth() === dob.getMonth() && today.getDate() < dob.getDate());
  if (beforeBirthday) age -= 1;
  return age;
}

/**
 * Approve / reject actions for a pending self-registration.
 *
 * These deliberately do not reuse the generic status-change action: approving
 * also allocates the member number and notifies the applicant, which only the
 * dedicated endpoints do.
 *
 * Approving opens a dialog rather than a plain confirmation because it is where
 * a paid tier legitimately enters the system — a human looking at the applicant
 * chooses it. The age check next to the dropdown is a warning and never a block:
 * clubs run honorary, reduced and family arrangements that break their own age
 * bands, and refusing them would send an admin into the database.
 */
export function RegistrationReviewActions({
  member,
  size = "sm",
}: RegistrationReviewActionsProps) {
  const t = useTranslations();
  const [approveOpen, setApproveOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [typeId, setTypeId] = useState<string>("");

  const { data: membershipTypes } = useMembershipTypes();
  const { mutateAsync: approve, isPending: isApproving } = useApproveMember();
  const { mutateAsync: reject, isPending: isRejecting } = useRejectMember();

  const busy = isApproving || isRejecting;

  const activeTypes = useMemo(
    () => (membershipTypes ?? []).filter((mt) => mt.is_active),
    [membershipTypes]
  );

  const prefilledTypeId = useMemo(() => {
    const current = activeTypes.find((mt) => mt.id === member.membership_type_id);
    if (current) return String(current.id);
    const fallback = activeTypes.find((mt) => mt.is_default);
    return fallback ? String(fallback.id) : "";
  }, [activeTypes, member.membership_type_id]);

  useEffect(() => {
    if (approveOpen) setTypeId(prefilledTypeId);
  }, [approveOpen, prefilledTypeId]);

  const selectedType: MembershipTypeData | undefined = activeTypes.find(
    (mt) => String(mt.id) === typeId
  );

  const age = ageOn(member.person.date_of_birth);
  let ageWarning: string | null = null;
  if (age !== null && selectedType) {
    if (selectedType.max_age !== null && age > selectedType.max_age) {
      ageWarning = t("members.registration.ageAboveMax", {
        age,
        type: selectedType.name,
        limit: selectedType.max_age,
      });
    } else if (selectedType.min_age !== null && age < selectedType.min_age) {
      ageWarning = t("members.registration.ageBelowMin", {
        age,
        type: selectedType.name,
        limit: selectedType.min_age,
      });
    }
  }

  async function handleApprove() {
    try {
      await approve({
        id: member.id,
        membershipTypeId: typeId ? Number(typeId) : undefined,
      });
      setApproveOpen(false);
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
        <Button size={size} disabled={busy} onClick={() => setApproveOpen(true)}>
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

      <Dialog open={approveOpen} onOpenChange={setApproveOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("members.registration.approveTitle")}</DialogTitle>
            <DialogDescription>
              {t("members.registration.approveDescription")}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <Label htmlFor="approve-membership-type">
              {t("members.membershipType")}
            </Label>
            <Select value={typeId} onValueChange={setTypeId}>
              <SelectTrigger id="approve-membership-type">
                <SelectValue placeholder={t("members.selectType")} />
              </SelectTrigger>
              <SelectContent>
                {activeTypes.map((mt) => (
                  <SelectItem key={mt.id} value={String(mt.id)}>
                    {mt.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {t("members.registration.membershipTypeHelp")}
            </p>
            {ageWarning && (
              <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
                {ageWarning} {t("members.registration.ageWarningOverride")}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setApproveOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button disabled={isApproving} onClick={handleApprove}>
              {t("members.registration.approve")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
