"use client";

import { useState } from "react";
import { usePermissions } from "@/features/auth/hooks/use-permissions";
import { useTranslations } from "next-intl";
import { useRouter } from "@/lib/i18n/routing";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { getErrorMessage } from "@/lib/errors";
import { Markdown } from "@/lib/markdown";
import { useGroups } from "@/features/groups/hooks/use-groups";
import { useMembershipTypes } from "@/features/members/hooks/use-members";
import {
  useAudiencePreview,
  useCreateAnnouncement,
  useSendAnnouncement,
  useUpdateAnnouncement,
} from "../hooks/use-announcements";
import type {
  AnnouncementData,
  TargetType,
} from "../services/announcements-api";

export function AnnouncementForm({
  announcement,
}: {
  announcement?: AnnouncementData;
}) {
  const t = useTranslations();
  const { has } = usePermissions();
  const canSend = has("communications.send");
  const router = useRouter();
  const isSent = announcement?.status === "sent";

  const [subject, setSubject] = useState(announcement?.subject ?? "");
  const [body, setBody] = useState(announcement?.body ?? "");
  const [targetType, setTargetType] = useState<TargetType>(
    announcement?.target_type ?? "all"
  );
  const [targetId, setTargetId] = useState<number | null>(
    announcement?.target_id ?? null
  );
  const [confirmOpen, setConfirmOpen] = useState(false);

  const { data: groups } = useGroups();
  const { data: membershipTypes } = useMembershipTypes();
  const createMutation = useCreateAnnouncement();
  const updateMutation = useUpdateAnnouncement();
  const sendMutation = useSendAnnouncement();
  // Audience preview is only meaningful for a saved announcement.
  const { data: audience } = useAudiencePreview(
    announcement?.id ?? 0,
    Boolean(announcement) && !isSent
  );

  const targetValid = targetType === "all" || targetId != null;
  const canSave = subject.trim().length > 0 && body.trim().length > 0 && targetValid;

  function buildPayload() {
    return {
      subject: subject.trim(),
      body,
      target_type: targetType,
      target_id: targetType === "all" ? null : targetId,
    };
  }

  async function handleSave() {
    try {
      if (announcement) {
        await updateMutation.mutateAsync({ id: announcement.id, data: buildPayload() });
        toast.success(t("toast.success.saved"));
      } else {
        const created = await createMutation.mutateAsync(buildPayload());
        toast.success(t("toast.success.saved"));
        // Move to the draft's page where audience preview + Send are available.
        router.push(`/communications/${created.id}`);
      }
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  async function handleSend() {
    // For a new announcement, create the draft first, then send it — one action
    // that ends in "sent". For an existing draft, send it directly.
    let id = announcement?.id ?? null;
    try {
      if (id === null) {
        const created = await createMutation.mutateAsync(buildPayload());
        id = created.id;
      }
      await sendMutation.mutateAsync(id);
      toast.success(t("communications.compose.sentToast"));
      setConfirmOpen(false);
      router.push(`/communications/${id}`);
    } catch (error) {
      toast.error(getErrorMessage(error));
      setConfirmOpen(false);
      // A just-created draft persisted even though the send failed (e.g. empty
      // audience) — take the user to it so they can fix targeting and retry.
      if (id !== null && !announcement) {
        router.push(`/communications/${id}`);
      }
    }
  }

  return (
    <div className="space-y-3 max-w-4xl">
      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-base">
            {t("communications.compose.contentTitle")}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 px-4 pb-3 pt-0">
          <div className="space-y-1">
            <label className="text-xs font-medium">
              {t("communications.compose.subject")}
            </label>
            <Input
              className="h-8"
              maxLength={200}
              value={subject}
              disabled={isSent}
              onChange={(e) => setSubject(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium">
              {t("communications.compose.body")}
            </label>
            <Textarea
              rows={8}
              value={body}
              disabled={isSent}
              onChange={(e) => setBody(e.target.value)}
              placeholder={t("communications.compose.bodyPlaceholder")}
            />
            <p className="text-xs text-muted-foreground">
              {t("communications.compose.markdownHint")}
            </p>
          </div>
          {body.trim() && (
            <div className="space-y-1">
              <label className="text-xs font-medium">
                {t("communications.compose.preview")}
              </label>
              <Markdown
                content={body}
                className="rounded-md border p-3 text-sm prose-sm [&_p]:my-1 [&_ul]:my-1 [&_ul]:list-disc [&_ul]:pl-5 [&_a]:text-primary [&_a]:underline"
              />
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-base">
            {t("communications.compose.audienceTitle")}
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2 sm:grid-cols-2 px-4 pb-3 pt-0">
          <div className="space-y-1">
            <label className="text-xs font-medium">
              {t("communications.compose.target")}
            </label>
            <Select
              value={targetType}
              disabled={isSent}
              onValueChange={(v) => {
                setTargetType(v as TargetType);
                setTargetId(null);
              }}
            >
              <SelectTrigger className="h-8">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">
                  {t("communications.target.all")}
                </SelectItem>
                <SelectItem value="group">
                  {t("communications.target.group")}
                </SelectItem>
                <SelectItem value="membership_type">
                  {t("communications.target.membership_type")}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          {targetType === "group" && (
            <div className="space-y-1">
              <label className="text-xs font-medium">
                {t("communications.target.group")}
              </label>
              <Select
                value={targetId ? String(targetId) : ""}
                disabled={isSent}
                onValueChange={(v) => setTargetId(Number(v))}
              >
                <SelectTrigger className="h-8">
                  <SelectValue placeholder={t("communications.compose.selectGroup")} />
                </SelectTrigger>
                <SelectContent>
                  {(groups ?? []).map((g) => (
                    <SelectItem key={g.id} value={String(g.id)}>
                      {g.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {targetType === "membership_type" && (
            <div className="space-y-1">
              <label className="text-xs font-medium">
                {t("communications.target.membership_type")}
              </label>
              <Select
                value={targetId ? String(targetId) : ""}
                disabled={isSent}
                onValueChange={(v) => setTargetId(Number(v))}
              >
                <SelectTrigger className="h-8">
                  <SelectValue placeholder={t("communications.compose.selectMembershipType")} />
                </SelectTrigger>
                <SelectContent>
                  {(membershipTypes ?? []).map((mt) => (
                    <SelectItem key={mt.id} value={String(mt.id)}>
                      {mt.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {announcement && !isSent && audience && (
            <p className="text-xs text-muted-foreground sm:col-span-2">
              {t("communications.compose.audienceCount", { count: audience.count })}
            </p>
          )}
        </CardContent>
      </Card>

      {isSent ? (
        <div className="flex items-center gap-2">
          <Badge>{t("communications.status.sent")}</Badge>
          <span className="text-sm text-muted-foreground">
            {t("communications.compose.sentRecipients", {
              count: announcement?.recipient_count ?? 0,
            })}
          </span>
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={handleSave}
            disabled={!canSave || createMutation.isPending || updateMutation.isPending}
          >
            {createMutation.isPending || updateMutation.isPending
              ? t("common.loading")
              : t("communications.compose.saveDraft")}
          </Button>
          {canSend && (
            <Button
              disabled={!canSave || createMutation.isPending || sendMutation.isPending}
              onClick={() => setConfirmOpen(true)}
            >
              {t("communications.compose.send")}
            </Button>
          )}
        </div>
      )}

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("communications.compose.confirmSendTitle")}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {announcement
              ? t("communications.compose.confirmSendBody", {
                  count: audience?.count ?? 0,
                })
              : t("communications.compose.confirmSendBodyNew")}
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              onClick={handleSend}
              disabled={createMutation.isPending || sendMutation.isPending}
            >
              {createMutation.isPending || sendMutation.isPending
                ? t("common.loading")
                : t("communications.compose.send")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
