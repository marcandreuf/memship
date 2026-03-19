"use client";

interface PlaceholderTabProps {
  message: string;
}

export function PlaceholderTab({ message }: PlaceholderTabProps) {
  return (
    <div className="flex items-center justify-center py-6 text-muted-foreground">
      <p className="text-sm">{message}</p>
    </div>
  );
}
