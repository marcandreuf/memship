"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Link, useRouter } from "@/lib/i18n/routing";
import { Button } from "@/components/ui/button";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FormSkeleton } from "@/components/ui/skeletons";
import { useQueryClient } from "@tanstack/react-query";
import { ClientApiError } from "@/lib/client-api";
import { useDeleteSpace, useSpace } from "@/features/bookings/hooks/use-bookings";
import { deleteSpace as deleteSpaceApi } from "@/features/bookings/services/bookings-api";
import { SpaceForm } from "@/features/bookings/components/space-form";
import { SlotsTab } from "@/features/bookings/components/slots-tab";
import { SpaceBookingsTab } from "@/features/bookings/components/space-bookings-tab";
import { usePermissions } from "@/features/auth/hooks/use-permissions";

export default function SpaceDetailPage() {
  const t = useTranslations();
  const { has } = usePermissions();
  const canWrite = has("bookings.write");
  const params = useParams();
  const router = useRouter();
  const id = Number(params.id);
  const { data: space, isLoading } = useSpace(id);
  const [editOpen, setEditOpen] = useState(false);
  const qc = useQueryClient();
  const deleteMutation = useDeleteSpace();
  const [confirmDialog, confirmAction] = useConfirmDialog();

  // Delete is the explicit destructive path (deactivation lives in the edit
  // form). The first attempt goes through the raw API call so the expected 409
  // skips the global error toast; it carries the affected-member count —
  // confirm it, then force.
  async function onDelete() {
    try {
      await deleteSpaceApi(id);
      qc.invalidateQueries({ queryKey: ["spaces"] });
      toast.success(t("toast.success.deleted"));
      router.push("/spaces");
    } catch (error) {
      if (error instanceof ClientApiError && error.status === 409) {
        const affected =
          (error.detail as unknown as { affected_members?: number })
            ?.affected_members ?? 0;
        confirmAction({
          title: t("bookings.spaces.confirmDelete"),
          description: t("bookings.spaces.deleteAffected", { count: affected }),
          cancelLabel: t("common.cancel"),
          confirmLabel: t("common.delete"),
          onConfirm: async () => {
            try {
              await deleteMutation.mutateAsync({ id, force: true });
              toast.success(t("toast.success.deleted"));
              router.push("/spaces");
            } catch {
              /* global handler */
            }
          },
        });
      }
    }
  }

  if (isLoading) return <FormSkeleton fields={3} />;
  if (!space)
    return (
      <p className="text-sm text-muted-foreground">
        {t("bookings.spaces.notFound")}
      </p>
    );

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <Link
            href="/spaces"
            className="text-xs text-muted-foreground hover:underline"
          >
            ← {t("bookings.spaces.title")}
          </Link>
          <h1 className="text-2xl font-bold">{space.name}</h1>
          <p className="text-sm text-muted-foreground">
            {space.open_time.slice(0, 5)}–{space.close_time.slice(0, 5)}
            {space.space_type ? ` · ${space.space_type}` : ""}
          </p>
        </div>
        <div className="flex gap-2">
          {confirmDialog}
          {canWrite && (<>
          <Dialog open={editOpen} onOpenChange={setEditOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm">
                {t("common.edit")}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{t("bookings.spaces.edit")}</DialogTitle>
              </DialogHeader>
              <SpaceForm space={space} onSuccess={() => setEditOpen(false)} />
            </DialogContent>
          </Dialog>
          <Button
            variant="outline"
            size="sm"
            className="text-destructive"
            disabled={deleteMutation.isPending}
            onClick={() =>
              confirmAction({
                title: t("bookings.spaces.confirmDelete"),
                cancelLabel: t("common.cancel"),
                confirmLabel: t("common.delete"),
                onConfirm: onDelete,
              })
            }
          >
            {t("common.delete")}
          </Button>
          </>)}
        </div>
      </div>

      <Tabs defaultValue="slots">
        <TabsList>
          <TabsTrigger value="slots">{t("bookings.slots.tab")}</TabsTrigger>
          <TabsTrigger value="bookings">
            {t("bookings.adminBookings.tab")}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="slots">
          <SlotsTab spaceId={id} />
        </TabsContent>
        <TabsContent value="bookings">
          <SpaceBookingsTab spaceId={id} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
