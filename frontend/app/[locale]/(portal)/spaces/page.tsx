"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/lib/i18n/routing";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TabContentSkeleton } from "@/components/ui/skeletons";
import { useSpaces } from "@/features/bookings/hooks/use-bookings";
import { SpaceForm } from "@/features/bookings/components/space-form";
import { usePermissions } from "@/features/auth/hooks/use-permissions";

export default function SpacesPage() {
  const t = useTranslations();
  const { has } = usePermissions();
  const canWrite = has("bookings.write");
  const { data: spaces = [], isLoading } = useSpaces();
  const [open, setOpen] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("bookings.spaces.title")}</h1>
        {canWrite && (
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button size="sm">{t("bookings.spaces.create")}</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{t("bookings.spaces.create")}</DialogTitle>
              </DialogHeader>
              <SpaceForm space={null} onSuccess={() => setOpen(false)} />
            </DialogContent>
          </Dialog>
        )}
      </div>

      <Card>
        <CardContent className="p-4 table-compact overflow-x-auto">
          {isLoading ? (
            <TabContentSkeleton />
          ) : !spaces.length ? (
            <p className="text-sm text-muted-foreground">
              {t("bookings.spaces.noSpaces")}
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("bookings.spaces.name")}</TableHead>
                  <TableHead>{t("bookings.spaces.type")}</TableHead>
                  <TableHead>{t("bookings.spaces.hours")}</TableHead>
                  <TableHead>{t("bookings.spaces.status")}</TableHead>
                  <TableHead>{t("common.actions")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {spaces.map((space) => (
                  <TableRow
                    key={space.id}
                    className={space.is_active ? undefined : "opacity-60"}
                  >
                    <TableCell className="font-medium">{space.name}</TableCell>
                    <TableCell>{space.space_type ?? "—"}</TableCell>
                    <TableCell>
                      {space.open_time.slice(0, 5)}–{space.close_time.slice(0, 5)}
                    </TableCell>
                    <TableCell>
                      <Badge variant={space.is_active ? "default" : "secondary"}>
                        {space.is_active
                          ? t("bookings.spaces.active")
                          : t("bookings.spaces.inactive")}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Button variant="outline" size="sm" asChild>
                        <Link href={`/spaces/${space.id}`}>
                          {t("bookings.spaces.manage")}
                        </Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
