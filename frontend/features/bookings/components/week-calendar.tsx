"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { TabContentSkeleton } from "@/components/ui/skeletons";
import {
  useAvailability,
  useAvailableSpaces,
  useCreateBooking,
} from "../hooks/use-bookings";
import type { AvailabilityCell } from "../services/bookings-api";

const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6];

function mondayOf(d: Date): Date {
  const copy = new Date(d);
  const day = (copy.getDay() + 6) % 7; // 0 = Monday
  copy.setDate(copy.getDate() - day);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

function toISODate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

const shortDate = (d: Date) =>
  `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`;

const hhmm = (t: string) => t.slice(0, 5);

export function WeekCalendar() {
  const t = useTranslations();
  const { data: spaces = [], isLoading: loadingSpaces } = useAvailableSpaces();
  const [spaceId, setSpaceId] = useState<number | null>(null);
  const [weekStartDate, setWeekStartDate] = useState<Date>(() =>
    mondayOf(new Date())
  );
  const [confirmDialog, confirmAction] = useConfirmDialog();
  const createBooking = useCreateBooking();

  useEffect(() => {
    if (spaceId === null && spaces.length) setSpaceId(spaces[0].id);
  }, [spaces, spaceId]);

  const weekStart = toISODate(weekStartDate);
  const { data: availability, isLoading: loadingAvailability } = useAvailability(
    spaceId ?? 0,
    weekStart,
    spaceId !== null
  );

  const cellsByWeekday = useMemo(() => {
    const map = new Map<number, AvailabilityCell[]>();
    for (const cell of availability?.cells ?? []) {
      const list = map.get(cell.weekday) ?? [];
      list.push(cell);
      map.set(cell.weekday, list);
    }
    for (const list of map.values())
      list.sort((a, b) => a.start_time.localeCompare(b.start_time));
    return map;
  }, [availability]);

  function book(cell: AvailabilityCell) {
    const waitlist = cell.cell_state === "full";
    confirmAction({
      title: waitlist
        ? t("bookings.book.confirmWaitlist")
        : t("bookings.book.confirmBook"),
      cancelLabel: t("common.cancel"),
      confirmLabel: waitlist
        ? t("bookings.book.joinWaitlist")
        : t("bookings.book.book"),
      onConfirm: async () => {
        try {
          const result = await createBooking.mutateAsync(cell.space_slot_id);
          toast.success(
            result.status === "waitlisted"
              ? t("bookings.book.waitlistedToast")
              : t("bookings.book.bookedToast")
          );
        } catch {
          /* global handler shows the error toast */
        }
      },
    });
  }

  if (loadingSpaces) return <TabContentSkeleton />;
  if (!spaces.length)
    return (
      <p className="text-sm text-muted-foreground">
        {t("bookings.book.noSpaces")}
      </p>
    );

  const rangeEnd = new Date(weekStartDate);
  rangeEnd.setDate(rangeEnd.getDate() + 6);

  return (
    <div className="space-y-4">
      {confirmDialog}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Select
          value={spaceId !== null ? String(spaceId) : undefined}
          onValueChange={(v) => setSpaceId(Number(v))}
        >
          <SelectTrigger className="w-56">
            <SelectValue placeholder={t("bookings.book.pickSpace")} />
          </SelectTrigger>
          <SelectContent>
            {spaces.map((s) => (
              <SelectItem key={s.id} value={String(s.id)}>
                {s.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="icon"
            aria-label={t("bookings.book.prev")}
            onClick={() => {
              const d = new Date(weekStartDate);
              d.setDate(d.getDate() - 7);
              setWeekStartDate(d);
            }}
          >
            <ChevronLeft className="size-4" />
          </Button>
          <span className="text-sm text-muted-foreground">
            {shortDate(weekStartDate)} – {shortDate(rangeEnd)}
          </span>
          <Button
            variant="outline"
            size="icon"
            aria-label={t("bookings.book.next")}
            onClick={() => {
              const d = new Date(weekStartDate);
              d.setDate(d.getDate() + 7);
              setWeekStartDate(d);
            }}
          >
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </div>

      {loadingAvailability ? (
        <TabContentSkeleton />
      ) : (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-7">
          {WEEKDAYS.map((wd) => {
            const dayDate = new Date(weekStartDate);
            dayDate.setDate(dayDate.getDate() + wd);
            const cells = cellsByWeekday.get(wd) ?? [];
            return (
              <div key={wd} className="rounded-lg border p-2">
                <div className="mb-2 text-center text-xs font-medium">
                  {t(`bookings.weekdays.${wd}`)}
                  <span className="ml-1 text-muted-foreground">
                    {shortDate(dayDate)}
                  </span>
                </div>
                <div className="space-y-2">
                  {cells.length === 0 ? (
                    <p className="text-center text-xs text-muted-foreground">—</p>
                  ) : (
                    cells.map((cell) => (
                      <SlotCell
                        key={cell.space_slot_id}
                        cell={cell}
                        onBook={() => book(cell)}
                        pending={createBooking.isPending}
                      />
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function SlotCell({
  cell,
  onBook,
  pending,
}: {
  cell: AvailabilityCell;
  onBook: () => void;
  pending: boolean;
}) {
  const t = useTranslations();
  const muted = cell.cell_state === "past" || cell.cell_state === "out_of_window";

  return (
    <div
      className={`rounded-md border p-2 text-xs ${muted ? "opacity-50" : ""}`}
    >
      <div className="font-medium">
        {hhmm(cell.start_time)}–{hhmm(cell.end_time)}
      </div>
      <div className="text-muted-foreground">
        {cell.booked_count}/{cell.capacity}
        {cell.waitlist_count > 0 ? ` · +${cell.waitlist_count}` : ""}
      </div>
      <div className="mt-1">
        {cell.my_status === "booked" ? (
          <Badge variant="default">{t("bookings.status.booked")}</Badge>
        ) : cell.my_status === "waitlisted" ? (
          <Badge variant="secondary">{t("bookings.status.waitlisted")}</Badge>
        ) : muted ? null : cell.cell_state === "full" ? (
          <Button
            variant="outline"
            size="sm"
            className="h-7 w-full"
            disabled={pending}
            onClick={onBook}
          >
            {t("bookings.book.joinWaitlist")}
          </Button>
        ) : (
          <Button
            size="sm"
            className="h-7 w-full"
            disabled={pending}
            onClick={onBook}
          >
            {t("bookings.book.book")}
          </Button>
        )}
      </div>
    </div>
  );
}
