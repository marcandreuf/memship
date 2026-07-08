"use client";

import { Download } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { downloadFile } from "@/lib/download";

interface ExportButtonProps {
  /** Proxy path of the CSV export, e.g. "/api/members/export.csv". */
  path: string;
  /** Current filter state — forwarded so the export matches the on-screen list. */
  params?: Record<string, string | number | undefined | null>;
}

export function ExportButton({ path, params }: ExportButtonProps) {
  const t = useTranslations();
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={() => downloadFile(path, params)}
    >
      <Download className="mr-2 h-4 w-4" />
      {t("export.csv")}
    </Button>
  );
}
