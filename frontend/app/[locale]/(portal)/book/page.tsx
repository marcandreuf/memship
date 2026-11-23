"use client";

import { Suspense } from "react";
import { useTranslations } from "next-intl";
import { TabContentSkeleton } from "@/components/ui/skeletons";
import { WeekCalendar } from "@/features/bookings/components/week-calendar";

export default function BookPage() {
  const t = useTranslations();
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">{t("bookings.book.title")}</h1>
      {/* The calendar reads the space and date a mail links to from the URL. */}
      <Suspense fallback={<TabContentSkeleton />}>
        <WeekCalendar />
      </Suspense>
    </div>
  );
}
