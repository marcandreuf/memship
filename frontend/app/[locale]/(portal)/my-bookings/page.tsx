"use client";

import { useTranslations } from "next-intl";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { MyBookingsList } from "@/features/bookings/components/my-bookings-list";

export default function MyBookingsPage() {
  const t = useTranslations();
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">{t("bookings.my.title")}</h1>
      <Tabs defaultValue="upcoming">
        <TabsList>
          <TabsTrigger value="upcoming">{t("bookings.my.upcoming")}</TabsTrigger>
          <TabsTrigger value="past">{t("bookings.my.past")}</TabsTrigger>
        </TabsList>
        <TabsContent value="upcoming">
          <MyBookingsList scope="upcoming" />
        </TabsContent>
        <TabsContent value="past">
          <MyBookingsList scope="past" />
        </TabsContent>
      </Tabs>
    </div>
  );
}
