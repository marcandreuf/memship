"use client";

import { useState, useCallback } from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "default" | "destructive";
  onConfirm: () => void;
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "OK",
  cancelLabel,
  variant = "destructive",
  onConfirm,
}: ConfirmDialogProps) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          {description && (
            <AlertDialogDescription>{description}</AlertDialogDescription>
          )}
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{cancelLabel}</AlertDialogCancel>
          <AlertDialogAction variant={variant} onClick={onConfirm}>
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

/**
 * Hook that replaces `window.confirm()` with a Shadcn AlertDialog.
 *
 * Usage:
 *   const [confirmDialog, confirmAction] = useConfirmDialog();
 *
 *   // In handler:
 *   confirmAction({
 *     title: "Delete this item?",
 *     onConfirm: async () => { await deleteMutation.mutateAsync(id); },
 *   });
 *
 *   // In JSX (render once, anywhere in the component):
 *   {confirmDialog}
 */
export function useConfirmDialog() {
  const [state, setState] = useState<{
    open: boolean;
    title: string;
    description?: string;
    confirmLabel?: string;
    cancelLabel?: string;
    variant?: "default" | "destructive";
    onConfirm: () => void;
  }>({
    open: false,
    title: "",
    onConfirm: () => {},
  });

  const confirm = useCallback(
    (opts: {
      title: string;
      description?: string;
      confirmLabel?: string;
      cancelLabel?: string;
      variant?: "default" | "destructive";
      onConfirm: () => void;
    }) => {
      setState({ ...opts, open: true });
    },
    []
  );

  const dialog = (
    <ConfirmDialog
      open={state.open}
      onOpenChange={(open) => setState((s) => ({ ...s, open }))}
      title={state.title}
      description={state.description}
      confirmLabel={state.confirmLabel}
      cancelLabel={state.cancelLabel}
      variant={state.variant}
      onConfirm={() => {
        setState((s) => ({ ...s, open: false }));
        state.onConfirm();
      }}
    />
  );

  return [dialog, confirm] as const;
}
