"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { useFormatters } from "@/hooks/use-formatters";
import { getErrorMessage } from "@/lib/errors";
import {
  useReminders,
  useCreateReminder,
  useUpdateReminder,
  useDeleteReminder,
} from "../hooks/use-reminders";
import type { Reminder } from "../services/reminders-api";

// Days from today, at local midnight. Negative = past.
function daysUntil(due: string): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(due + "T00:00:00");
  return Math.round((target.getTime() - today.getTime()) / 86_400_000);
}

function DueBadge({ due }: { due: string }) {
  const t = useTranslations();
  const { formatDate } = useFormatters();
  const days = daysUntil(due);

  let variant: "destructive" | "secondary" | "outline" = "outline";
  let label = formatDate(due);
  if (days < 0) {
    variant = "destructive";
    label = t("notes.overdue");
  } else if (days === 0) {
    variant = "destructive";
    label = t("notes.today");
  } else if (days <= 7) {
    variant = "secondary";
  }

  return (
    <Badge variant={variant} className="shrink-0 text-xs" title={formatDate(due)}>
      {label}
    </Badge>
  );
}

function ReminderRow({ reminder }: { reminder: Reminder }) {
  const t = useTranslations();
  const update = useUpdateReminder();
  const remove = useDeleteReminder();

  return (
    <div className="flex items-start gap-2 rounded-md border p-2">
      <Checkbox
        className="mt-0.5"
        aria-label={t("notes.markDone")}
        checked={reminder.is_done}
        disabled={update.isPending}
        onCheckedChange={() =>
          update.mutate({ id: reminder.id, data: { is_done: true } })
        }
      />
      <p className="min-w-0 flex-1 break-words text-sm">{reminder.content}</p>
      {reminder.due_date ? (
        <DueBadge due={reminder.due_date} />
      ) : (
        <Badge variant="outline" className="shrink-0 text-xs text-muted-foreground">
          {t("notes.note")}
        </Badge>
      )}
      <Button
        variant="ghost"
        size="icon"
        className="size-6 shrink-0 text-muted-foreground hover:text-destructive"
        aria-label={t("notes.delete")}
        disabled={remove.isPending}
        onClick={() =>
          remove.mutate(reminder.id, {
            onSuccess: () => toast.success(t("notes.deletedToast")),
            onError: (e) => toast.error(getErrorMessage(e)),
          })
        }
      >
        <Trash2 className="size-3.5" />
      </Button>
    </div>
  );
}

export function ReminderList() {
  const t = useTranslations();
  const { data: reminders, isLoading } = useReminders(true);
  const create = useCreateReminder();
  const [content, setContent] = useState("");
  const [dueDate, setDueDate] = useState("");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = content.trim();
    if (!trimmed) return;
    create.mutate(
      { content: trimmed, due_date: dueDate || null },
      {
        onSuccess: () => {
          setContent("");
          setDueDate("");
          toast.success(t("notes.addedToast"));
        },
        onError: (err) => toast.error(getErrorMessage(err)),
      }
    );
  };

  return (
    <Card className="py-3 gap-2">
      <CardHeader className="px-4">
        <CardTitle className="text-base">{t("notes.title")}</CardTitle>
      </CardHeader>
      <CardContent className="px-4 space-y-3">
        <form onSubmit={submit} className="space-y-2">
          <Input
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder={t("notes.addPlaceholder")}
            maxLength={2000}
          />
          <div className="flex gap-2">
            <Input
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              className="flex-1"
            />
            <Button type="submit" size="sm" disabled={!content.trim() || create.isPending}>
              <Plus className="size-4" />
              {t("notes.add")}
            </Button>
          </div>
        </form>

        {isLoading ? null : !reminders?.length ? (
          <p className="py-2 text-center text-sm text-muted-foreground">
            {t("notes.empty")}
          </p>
        ) : (
          <div className="space-y-2">
            {reminders.map((r) => (
              <ReminderRow key={r.id} reminder={r} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
