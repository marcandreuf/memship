"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "@/lib/i18n/routing";
import { Button } from "@/components/ui/button";
import { MemberForm } from "@/features/members/components/member-form";
import { useCreateMember } from "@/features/members/hooks/use-members";

export default function NewMemberPage() {
  const t = useTranslations();
  const router = useRouter();
  const { mutateAsync: create, isPending } = useCreateMember();

  return (
    <div className="space-y-4">
      <Button variant="outline" onClick={() => router.push("/members")}>
        {t("common.back")}
      </Button>
      <MemberForm
        onSubmit={async (data) => {
          await create({
            ...data,
            email: data.email || undefined,
            date_of_birth: data.date_of_birth || undefined,
            gender: data.gender || undefined,
            national_id: data.national_id || undefined,
            internal_notes: data.internal_notes || undefined,
          });
          router.push("/members");
        }}
        isSubmitting={isPending}
      />
    </div>
  );
}
