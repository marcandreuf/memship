"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "@/lib/i18n/routing";
import { Button } from "@/components/ui/button";
import { EntityForm } from "@/features/entities/components/entity-form";
import { useCreateEntity } from "@/features/entities/hooks/use-entities";

export default function NewEntityPage() {
  const t = useTranslations();
  const router = useRouter();
  const { mutateAsync: create, isPending } = useCreateEntity();

  return (
    <div className="space-y-4">
      <Button variant="outline" onClick={() => router.push("/entities")}>
        {t("common.back")}
      </Button>
      <h1 className="text-2xl font-bold">{t("entities.newEntity")}</h1>
      <EntityForm
        onSubmit={async (data) => {
          const created = await create({
            ...data,
            legal_name: data.legal_name || undefined,
            national_id: data.national_id || undefined,
            email: data.email || undefined,
          });
          router.push(`/entities/${created.id}`);
        }}
        isSubmitting={isPending}
      />
    </div>
  );
}
