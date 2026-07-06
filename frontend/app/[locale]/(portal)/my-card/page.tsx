"use client";

import { useTranslations } from "next-intl";
import { IdCard } from "lucide-react";
import { useMyCard } from "@/features/member-card/hooks/use-member-card";
import { MemberCard } from "@/features/member-card/components/member-card";
import { FormSkeleton } from "@/components/ui/skeletons";

export default function MyCardPage() {
  const t = useTranslations();
  const { data: card, isLoading, isError } = useMyCard();

  return (
    <div className="space-y-4">
      <h1 className="flex items-center gap-2 text-2xl font-bold">
        <IdCard className="h-6 w-6" />
        {t("memberCard.title")}
      </h1>

      {isLoading ? (
        <FormSkeleton fields={4} />
      ) : isError || !card ? (
        <p className="py-8 text-center text-muted-foreground">
          {t("memberCard.unavailable")}
        </p>
      ) : (
        <MemberCard card={card} />
      )}
    </div>
  );
}
