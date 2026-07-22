"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
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
import { mapApiErrorsToForm } from "@/lib/errors";
import {
  useCreateSlot,
  useDeleteSlot,
  useSlots,
  useUpdateSlot,
} from "../hooks/use-bookings";
import type { SpaceSlot } from "../services/bookings-api";

const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6];
const toTimeInput = (s: string) => s.slice(0, 5);

const slotSchema = z
  .object({
    weekday: z.coerce.number().int().min(0).max(6),
    start_time: z.string().regex(/^\d{2}:\d{2}$/, "HH:MM"),
    end_time: z.string().regex(/^\d{2}:\d{2}$/, "HH:MM"),
    capacity: z.coerce.number().int().min(1),
    is_active: z.boolean(),
  })
  .superRefine((data, ctx) => {
    if (data.end_time && data.start_time && data.end_time <= data.start_time) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["end_time"],
        message: "end after start",
      });
    }
  });

type SlotFormValues = z.infer<typeof slotSchema>;

export function SlotsTab({ spaceId }: { spaceId: number }) {
  const t = useTranslations();
  const { data: slots = [], isLoading } = useSlots(spaceId);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<SpaceSlot | null>(null);

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Dialog
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
          <DialogContent>
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
        </Dialog>
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
                <TableHead>{t("bookings.slots.weekday")}</TableHead>
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
  const deleteMutation = useDeleteSlot(spaceId);
  const [confirmDialog, confirmAction] = useConfirmDialog();

  return (
    <TableRow className={slot.is_active ? undefined : "opacity-60"}>
      <TableCell className="font-medium">
        {t(`bookings.weekdays.${slot.weekday}`)}
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
          <Button variant="outline" size="sm" onClick={onEdit}>
            {t("common.edit")}
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={deleteMutation.isPending}
            onClick={() =>
              confirmAction({
                title: t("bookings.slots.confirmDelete"),
                cancelLabel: t("common.cancel"),
                confirmLabel: t("common.delete"),
                onConfirm: async () => {
                  try {
                    await deleteMutation.mutateAsync(slot.id);
                    toast.success(t("toast.success.deleted"));
                  } catch {
                    /* global handler */
                  }
                },
              })
            }
          >
            {t("common.delete")}
          </Button>
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

  const form = useForm<SlotFormValues>({
    resolver: zodResolver(slotSchema),
    defaultValues: {
      weekday: slot?.weekday ?? 0,
      start_time: slot ? toTimeInput(slot.start_time) : "10:00",
      end_time: slot ? toTimeInput(slot.end_time) : "11:00",
      capacity: slot?.capacity ?? 1,
      is_active: slot?.is_active ?? true,
    },
  });

  async function onSubmit(data: SlotFormValues) {
    try {
      if (slot) {
        await updateMutation.mutateAsync({ slotId: slot.id, data });
      } else {
        await createMutation.mutateAsync(data);
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
          name="weekday"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t("bookings.slots.weekday")}</FormLabel>
              <Select
                value={String(field.value)}
                onValueChange={(v) => field.onChange(Number(v))}
              >
                <FormControl>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {WEEKDAYS.map((d) => (
                    <SelectItem key={d} value={String(d)}>
                      {t(`bookings.weekdays.${d}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />
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
                <FormMessage />
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
        <Button type="submit" disabled={isPending} className="w-full">
          {isPending ? t("common.loading") : t("common.save")}
        </Button>
      </form>
    </Form>
  );
}
