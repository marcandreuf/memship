"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Repeat } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { TabContentSkeleton } from "@/components/ui/skeletons";
import { useFormatters } from "@/hooks/use-formatters";
import { ClientApiError } from "@/lib/client-api";
import { mapApiErrorsToForm } from "@/lib/errors";
import { useQueryClient } from "@tanstack/react-query";
import { usePermissions } from "@/features/auth/hooks/use-permissions";
import {
  useCreateSlot,
  useDeleteSlot,
  useSlots,
  useUpdateSlot,
} from "../hooks/use-bookings";
import {
  deleteSlot as deleteSlotApi,
  type SpaceSlot,
} from "../services/bookings-api";

const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6];
const toTimeInput = (s: string) => s.slice(0, 5);

// "YYYY-MM-DD" → weekday 0=Mon … 6=Sun, parsed as a local date (a bare
// new Date(str) would be UTC midnight and can shift the day).
function isoWeekday(dateStr: string): number {
  const [y, m, d] = dateStr.split("-").map(Number);
  return (new Date(y, m - 1, d).getDay() + 6) % 7;
}

function todayStr(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

const slotSchema = z
  .object({
    slot_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "YYYY-MM-DD"),
    all_day: z.boolean(),
    start_time: z.string(),
    end_time: z.string(),
    capacity: z.coerce.number().int().min(1),
    is_active: z.boolean(),
    repeat_enabled: z.boolean(),
    repeat_weekdays: z.array(z.number().int().min(0).max(6)),
    repeat_interval: z.coerce.number().int().min(1).max(12),
    repeat_count: z.coerce.number().int().min(1).max(52),
    apply_to: z.enum(["one", "upcoming"]),
  })
  .superRefine((data, ctx) => {
    if (!data.all_day) {
      if (!/^\d{2}:\d{2}$/.test(data.start_time)) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["start_time"], message: "HH:MM" });
      }
      if (!/^\d{2}:\d{2}$/.test(data.end_time)) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["end_time"], message: "HH:MM" });
      }
      if (data.end_time && data.start_time && data.end_time <= data.start_time) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["end_time"],
          message: "end after start",
        });
      }
    }
    // Past guard (client side; the backend re-checks in the org timezone).
    const today = todayStr();
    if (data.slot_date < today) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["slot_date"],
        message: "past",
      });
    } else if (!data.all_day && data.slot_date === today) {
      const now = new Date();
      const hhmm = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
      if (data.start_time <= hhmm) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["start_time"],
          message: "past",
        });
      }
    }
  });

type SlotFormValues = z.infer<typeof slotSchema>;

export function SlotsTab({ spaceId }: { spaceId: number }) {
  const t = useTranslations();
  const { has } = usePermissions();
  const canWrite = has("bookings.write");
  const { data: slots = [], isLoading } = useSlots(spaceId);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<SpaceSlot | null>(null);

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        {canWrite && <Dialog
          open={open}
          onOpenChange={(o) => {
            setOpen(o);
            if (!o) setEditing(null);
          }}
        >
          <DialogTrigger asChild>
            <Button variant="outline" size="sm" onClick={() => setEditing(null)}>
              {t("bookings.slots.add")}
            </Button>
          </DialogTrigger>
          <DialogContent className="max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>
                {editing ? t("bookings.slots.edit") : t("bookings.slots.add")}
              </DialogTitle>
            </DialogHeader>
            <SlotForm
              spaceId={spaceId}
              slot={editing}
              onSuccess={() => {
                setOpen(false);
                setEditing(null);
              }}
            />
          </DialogContent>
        </Dialog>}
      </div>

      <div className="table-compact overflow-x-auto">
        {isLoading ? (
          <TabContentSkeleton />
        ) : !slots.length ? (
          <p className="text-sm text-muted-foreground">
            {t("bookings.slots.noSlots")}
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("bookings.slots.date")}</TableHead>
                <TableHead>{t("bookings.slots.start")}</TableHead>
                <TableHead>{t("bookings.slots.end")}</TableHead>
                <TableHead>{t("bookings.slots.capacity")}</TableHead>
                <TableHead>{t("common.actions")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {slots.map((slot) => (
                <SlotRow
                  key={slot.id}
                  spaceId={spaceId}
                  slot={slot}
                  onEdit={() => {
                    setEditing(slot);
                    setOpen(true);
                  }}
                />
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}

function SlotRow({
  spaceId,
  slot,
  onEdit,
}: {
  spaceId: number;
  slot: SpaceSlot;
  onEdit: () => void;
}) {
  const t = useTranslations();
  const { has } = usePermissions();
  const canWrite = has("bookings.write");
  const { formatDate } = useFormatters();
  const qc = useQueryClient();
  const updateMutation = useUpdateSlot(spaceId);
  const deleteMutation = useDeleteSlot(spaceId);
  const [confirmDialog, confirmAction] = useConfirmDialog();

  async function onDelete() {
    // First attempt without force, via the raw API call so the expected 409
    // skips the global error toast. The 409 carries how many members hold
    // active bookings; confirm with that count, then force. Deactivation is
    // the non-destructive default — delete is the explicit destructive path.
    try {
      await deleteSlotApi(spaceId, slot.id);
      qc.invalidateQueries({ queryKey: ["space-slots", spaceId] });
      toast.success(t("toast.success.deleted"));
    } catch (error) {
      if (error instanceof ClientApiError && error.status === 409) {
        const affected =
          (error.detail as unknown as { affected_members?: number })
            ?.affected_members ?? 0;
        confirmAction({
          title: t("bookings.slots.confirmDelete"),
          description: t("bookings.slots.deleteAffected", { count: affected }),
          cancelLabel: t("common.cancel"),
          confirmLabel: t("common.delete"),
          onConfirm: async () => {
            try {
              await deleteMutation.mutateAsync({ slotId: slot.id, force: true });
              toast.success(t("toast.success.deleted"));
            } catch {
              /* global handler */
            }
          },
        });
      }
    }
  }

  return (
    <TableRow className={slot.is_active ? undefined : "opacity-60"}>
      <TableCell className="font-medium">
        {t(`bookings.weekdays.${isoWeekday(slot.slot_date)}`)}{" "}
        {formatDate(slot.slot_date)}
        {slot.series_id && (
          <Repeat
            className="ml-1 inline size-3 text-muted-foreground"
            aria-label={t("bookings.slots.series")}
          />
        )}
        {!slot.is_active && (
          <Badge variant="secondary" className="ml-2">
            {t("bookings.slots.inactive")}
          </Badge>
        )}
      </TableCell>
      <TableCell>{toTimeInput(slot.start_time)}</TableCell>
      <TableCell>{toTimeInput(slot.end_time)}</TableCell>
      <TableCell>{slot.capacity}</TableCell>
      <TableCell>
        <div className="flex gap-2">
          {confirmDialog}
          {canWrite && (<>
          <Button variant="outline" size="sm" onClick={onEdit}>
            {t("common.edit")}
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={updateMutation.isPending}
            onClick={async () => {
              try {
                await updateMutation.mutateAsync({
                  slotId: slot.id,
                  data: { is_active: !slot.is_active },
                });
                toast.success(t("toast.success.saved"));
              } catch {
                /* global handler */
              }
            }}
          >
            {slot.is_active
              ? t("bookings.slots.deactivate")
              : t("bookings.slots.activate")}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-destructive"
            disabled={deleteMutation.isPending}
            onClick={() =>
              confirmAction({
                title: t("bookings.slots.confirmDelete"),
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
      </TableCell>
    </TableRow>
  );
}

function SlotForm({
  spaceId,
  slot,
  onSuccess,
}: {
  spaceId: number;
  slot: SpaceSlot | null;
  onSuccess: () => void;
}) {
  const t = useTranslations();
  const createMutation = useCreateSlot(spaceId);
  const updateMutation = useUpdateSlot(spaceId);
  const isSeriesEdit = Boolean(slot && slot.series_id && slot.series_size_upcoming > 1);

  const form = useForm<SlotFormValues>({
    resolver: zodResolver(slotSchema),
    defaultValues: {
      slot_date: slot?.slot_date ?? todayStr(),
      all_day: false,
      start_time: slot ? toTimeInput(slot.start_time) : "10:00",
      end_time: slot ? toTimeInput(slot.end_time) : "11:00",
      capacity: slot?.capacity ?? 1,
      is_active: slot?.is_active ?? true,
      repeat_enabled: false,
      repeat_weekdays: [],
      repeat_interval: 1,
      repeat_count: 4,
      apply_to: "one",
    },
  });
  const allDay = form.watch("all_day");
  const repeatEnabled = form.watch("repeat_enabled");

  async function onSubmit(data: SlotFormValues) {
    const payload = {
      slot_date: data.slot_date,
      all_day: data.all_day,
      ...(data.all_day
        ? {}
        : { start_time: data.start_time, end_time: data.end_time }),
      capacity: data.capacity,
      is_active: data.is_active,
    };
    try {
      if (slot) {
        await updateMutation.mutateAsync({
          slotId: slot.id,
          data: payload,
          applyTo: isSeriesEdit ? data.apply_to : "one",
        });
      } else {
        const created = await createMutation.mutateAsync({
          ...payload,
          ...(data.repeat_enabled
            ? {
                repeat: {
                  weekdays: data.repeat_weekdays.length
                    ? data.repeat_weekdays
                    : [isoWeekday(data.slot_date)],
                  interval_weeks: data.repeat_interval,
                  count: data.repeat_count,
                },
              }
            : {}),
        });
        if (created.length > 1) {
          toast.success(
            t("bookings.slots.createdSeries", { count: created.length })
          );
          onSuccess();
          return;
        }
      }
      toast.success(t("toast.success.saved"));
      onSuccess();
    } catch (error) {
      mapApiErrorsToForm(error, form);
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="slot_date"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t("bookings.slots.date")}</FormLabel>
              <FormControl>
                <Input type="date" min={todayStr()} {...field} />
              </FormControl>
              {form.formState.errors.slot_date?.message === "past" ? (
                <p className="text-sm text-destructive">
                  {t("bookings.slots.pastDate")}
                </p>
              ) : (
                <FormMessage />
              )}
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="all_day"
          render={({ field }) => (
            <FormItem className="flex items-center gap-2">
              <FormControl>
                <Checkbox checked={field.value} onCheckedChange={field.onChange} />
              </FormControl>
              <FormLabel className="!mt-0">
                {t("bookings.slots.allDay")}
              </FormLabel>
            </FormItem>
          )}
        />
        {!allDay && (
          <div className="grid gap-3 sm:grid-cols-2">
            <FormField
              control={form.control}
              name="start_time"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("bookings.slots.start")}</FormLabel>
                  <FormControl>
                    <Input type="time" {...field} />
                  </FormControl>
                  {form.formState.errors.start_time?.message === "past" ? (
                    <p className="text-sm text-destructive">
                      {t("bookings.slots.pastTime")}
                    </p>
                  ) : (
                    <FormMessage />
                  )}
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="end_time"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("bookings.slots.end")}</FormLabel>
                  <FormControl>
                    <Input type="time" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        )}
        <FormField
          control={form.control}
          name="capacity"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t("bookings.slots.capacity")}</FormLabel>
              <FormControl>
                <Input type="number" min={1} {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {!slot && (
          <>
            <FormField
              control={form.control}
              name="repeat_enabled"
              render={({ field }) => (
                <FormItem className="flex items-center gap-2">
                  <FormControl>
                    <Checkbox
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  </FormControl>
                  <FormLabel className="!mt-0">
                    {t("bookings.slots.repeat")}
                  </FormLabel>
                </FormItem>
              )}
            />
            {repeatEnabled && (
              <div className="space-y-3 rounded-md border p-3">
                <FormField
                  control={form.control}
                  name="repeat_weekdays"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("bookings.slots.repeatWeekdays")}</FormLabel>
                      <div className="flex flex-wrap gap-1">
                        {WEEKDAYS.map((d) => {
                          const selected = field.value.includes(d);
                          return (
                            <Button
                              key={d}
                              type="button"
                              size="sm"
                              variant={selected ? "default" : "outline"}
                              className="h-7 px-2 text-xs"
                              onClick={() =>
                                field.onChange(
                                  selected
                                    ? field.value.filter((v) => v !== d)
                                    : [...field.value, d].sort()
                                )
                              }
                            >
                              {t(`bookings.weekdays.${d}`)}
                            </Button>
                          );
                        })}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {t("bookings.slots.repeatWeekdaysHint")}
                      </p>
                    </FormItem>
                  )}
                />
                <div className="grid gap-3 sm:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="repeat_interval"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t("bookings.slots.repeatInterval")}</FormLabel>
                        <FormControl>
                          <Input type="number" min={1} max={12} {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="repeat_count"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t("bookings.slots.repeatCount")}</FormLabel>
                        <FormControl>
                          <Input type="number" min={1} max={52} {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              </div>
            )}
          </>
        )}

        {isSeriesEdit && (
          <FormField
            control={form.control}
            name="apply_to"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("bookings.slots.applyTo")}</FormLabel>
                <Select value={field.value} onValueChange={field.onChange}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    <SelectItem value="one">
                      {t("bookings.slots.applyToOne")}
                    </SelectItem>
                    <SelectItem value="upcoming">
                      {t("bookings.slots.applyToUpcoming", {
                        count: slot?.series_size_upcoming ?? 0,
                      })}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </FormItem>
            )}
          />
        )}

        <FormField
          control={form.control}
          name="is_active"
          render={({ field }) => (
            <FormItem className="flex items-center gap-2">
              <FormControl>
                <Checkbox
                  checked={field.value}
                  onCheckedChange={field.onChange}
                />
              </FormControl>
              <FormLabel className="!mt-0">
                {t("bookings.slots.active")}
              </FormLabel>
            </FormItem>
          )}
        />
        {form.formState.errors.root && (
          <p className="text-sm text-destructive">
            {form.formState.errors.root.message}
          </p>
        )}
        <Button type="submit" disabled={isPending} className="w-full">
          {isPending ? t("common.loading") : t("common.save")}
        </Button>
      </form>
    </Form>
  );
}
