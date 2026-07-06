"use client";

import { useTranslations } from "next-intl";
import { useMemberCard } from "../hooks/use-member-card";
import { MemberCard } from "./member-card";
import { TabContentSkeleton } from "@/components/ui/skeletons";

/**
 * Admin view of a member's card on the member detail page. Reuses the member
 * card component, but sources the QR + PDF from the admin `/members/{id}/card/*`
 * endpoints so an admin can view and print any member's card.
 */
export function MemberCardTab({ memberId }: { memberId: number }) {
  const t = useTranslations();
  const { data: card, isLoading, isError } = useMemberCard(memberId);

  if (isLoading) return <TabContentSkeleton />;

  if (isError || !card) {
    return (
      <p className="py-4 text-sm text-muted-foreground">
        {t("memberCard.unavailable")}
      </p>
    );
  }

  return (
    <MemberCard
      card={card}
      qrSrc={`/api/members/${memberId}/card/qr.svg`}
      pdfHref={`/api/members/${memberId}/card/pdf`}
    />
  );
}
