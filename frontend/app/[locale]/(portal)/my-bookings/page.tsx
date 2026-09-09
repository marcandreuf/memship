"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Tabs, TabsContent, TabsNav } from "@/components/ui/tabs";
import { MyBookingsList } from "@/features/bookings/components/my-bookings-list";

export default function MyBookingsPage() {
  const t = useTranslations();
  const [tab, setTab] = useState("upcoming");
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">{t("bookings.my.title")}</h1>
      <Tabs value={tab} onValueChange={setTab}>
        <TabsNav
          collapse="sm"
          value={tab}
          onValueChange={setTab}
          items={[
            { value: "upcoming", label: t("bookings.my.upcoming") },
            { value: "past", label: t("bookings.my.past") },
          ]}
        />
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
