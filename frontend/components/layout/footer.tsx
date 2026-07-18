"use client";

import { useTranslations } from "next-intl";

import { useVersion } from "@/features/system/hooks/use-version";

export function AppFooter() {
  const t = useTranslations();
  const { data } = useVersion();

  return (
    <footer className="border-t px-4 py-3 text-center text-xs text-muted-foreground md:px-6">
      {t("app.name")}
      {data?.version ? ` · ${t("footer.version", { version: data.version })}` : ""}
    </footer>
  );
}
