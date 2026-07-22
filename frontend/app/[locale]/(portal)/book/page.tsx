"use client";

import { useTranslations } from "next-intl";
import { WeekCalendar } from "@/features/bookings/components/week-calendar";

export default function BookPage() {
  const t = useTranslations();
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">{t("bookings.book.title")}</h1>
      <WeekCalendar />
    </div>
  );
}
