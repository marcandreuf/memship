"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Link } from "@/lib/i18n/routing";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FormSkeleton } from "@/components/ui/skeletons";
import { useSpace } from "@/features/bookings/hooks/use-bookings";
import { SpaceForm } from "@/features/bookings/components/space-form";
import { SlotsTab } from "@/features/bookings/components/slots-tab";
import { SpaceBookingsTab } from "@/features/bookings/components/space-bookings-tab";

export default function SpaceDetailPage() {
  const t = useTranslations();
  const params = useParams();
  const id = Number(params.id);
  const { data: space, isLoading } = useSpace(id);
  const [editOpen, setEditOpen] = useState(false);

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
