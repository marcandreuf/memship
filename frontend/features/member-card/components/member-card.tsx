"use client";

import { useTranslations } from "next-intl";
import { Download, QrCode } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import type { CardData } from "../services/member-card-api";

function initialsOf(fullName: string): string {
  const parts = fullName.trim().split(/\s+/);
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return `${first}${last}`.toUpperCase();
}

const ACTIVE_STATUS = "active";

export function MemberCard({ card }: { card: CardData }) {
  const t = useTranslations();
  const accent = card.organization.brand_color || undefined;
  const isActive = card.status === ACTIVE_STATUS;

  const photoSrc = card.photo_url
    ? `/api/uploads${card.photo_url.replace("/uploads", "")}`
    : null;

  return (
    <Card className="max-w-md overflow-hidden">
      <div className="h-2" style={{ backgroundColor: accent ?? "var(--primary)" }} />
      <CardContent className="p-5 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold" style={{ color: accent }}>
              {card.organization.name}
            </p>
          </div>
          <span
            className={cn(
              "shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-white",
              isActive ? "bg-green-600" : "bg-red-600"
            )}
          >
            {t(`memberCard.status.${card.status}`)}
          </span>
        </div>

        <div className="flex items-center gap-4">
          <Avatar className="h-16 w-16">
            {photoSrc ? <AvatarImage src={photoSrc} alt={card.full_name} /> : null}
            <AvatarFallback className="text-lg font-semibold">
              {initialsOf(card.full_name)}
            </AvatarFallback>
          </Avatar>
          <div className="min-w-0">
            <p className="truncate text-lg font-bold">{card.full_name}</p>
            <p className="font-mono text-sm tracking-wider text-muted-foreground">
              {card.member_number}
            </p>
          </div>
        </div>

        <div className="flex flex-col items-center gap-2 rounded-lg border bg-muted/30 p-4">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/api/me/card/qr.svg"
            alt={t("memberCard.qrAlt")}
            className="h-40 w-40"
          />
          <p className="flex items-center gap-1 text-xs text-muted-foreground">
            <QrCode className="h-3 w-3" />
            {t("memberCard.qrHint")}
          </p>
        </div>

        <Button asChild variant="outline" className="w-full">
          <a href="/api/me/card/pdf" target="_blank" rel="noopener noreferrer">
            <Download className="mr-2 h-4 w-4" />
            {t("memberCard.downloadPdf")}
          </a>
        </Button>
      </CardContent>
    </Card>
  );
}
