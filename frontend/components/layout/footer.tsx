"use client";

import { useTranslations } from "next-intl";

import { useVersion } from "@/features/system/hooks/use-version";

const SOURCE_URL = "https://github.com/marcandreuf/memship";
const LICENSE_URL = `${SOURCE_URL}/blob/main/LICENSE`;

export function AppFooter() {
  const t = useTranslations();
  const { data } = useVersion();

  return (
    <footer className="border-t px-4 py-3 text-xs text-muted-foreground md:px-6">
      <div className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1">
        <span>
          {t("app.name")}
          {data?.version
            ? ` · ${t("footer.version", { version: data.version })}`
            : ""}
        </span>
        {/* Decorative: without aria-hidden each separator is announced between
            the two links. */}
        <span aria-hidden="true">·</span>
        <a
          href={LICENSE_URL}
          target="_blank"
          rel="noreferrer"
          className="underline underline-offset-4 hover:text-foreground"
        >
          {t("footer.license")}
        </a>
        <span aria-hidden="true">·</span>
        <a
          href={SOURCE_URL}
          target="_blank"
          rel="noreferrer"
          className="underline underline-offset-4 hover:text-foreground"
        >
          {t("footer.source")}
        </a>
      </div>
    </footer>
  );
}
