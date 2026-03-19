"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/lib/i18n/routing";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Pagination } from "@/components/entity/pagination";
import {
  useMyRegistrations,
  useCancelRegistration,
} from "@/features/activities/hooks/use-registrations";
import { useActivity } from "@/features/activities/hooks/use-activities";
import type { RegistrationData } from "@/features/activities/services/registrations-api";

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  confirmed: "default",
  waitlist: "secondary",
  cancelled: "destructive",
  pending: "outline",
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function RegistrationCard({ registration }: { registration: RegistrationData }) {
  const t = useTranslations();
  const { data: activity } = useActivity(registration.activity_id);
  const cancelMutation = useCancelRegistration();

  const canCancel = registration.status === "confirmed" || registration.status === "waitlist";

  return (
    <Card>
      <CardContent className="py-3 px-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <Link
              href={`/activities/${registration.activity_id}`}
              className="font-medium hover:underline"
            >
              {activity?.name || `Activity #${registration.activity_id}`}
            </Link>
            {activity && (
              <p className="text-xs text-muted-foreground mt-0.5">
                {formatDate(activity.starts_at)} — {formatDate(activity.ends_at)}
                {activity.location && ` · ${activity.location}`}
              </p>
            )}
            <p className="text-xs text-muted-foreground mt-0.5">
              {t("activities.registration.registeredOn")}: {formatDate(registration.created_at)}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Badge variant={STATUS_VARIANTS[registration.status] || "outline"}>
              {t(`activities.registration.status.${registration.status}`)}
            </Badge>
            {canCancel && (
              <Button
                variant="outline"
                size="xs"
                onClick={() => {
                  if (confirm(t("activities.registration.confirmCancel"))) {
                    cancelMutation.mutate({ id: registration.id });
                  }
                }}
                disabled={cancelMutation.isPending}
              >
                {t("common.cancel")}
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function MyActivitiesPage() {
  const t = useTranslations();
  const [page, setPage] = useState(1);
  const { data, isLoading } = useMyRegistrations({ page, per_page: 20 });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">{t("activities.registration.myActivities")}</h1>

      {isLoading ? (
        <div className="py-8 text-center text-muted-foreground">{t("common.loading")}</div>
      ) : !data?.items.length ? (
        <div className="py-8 text-center text-muted-foreground">
          {t("activities.registration.noMyActivities")}
        </div>
      ) : (
        <>
          <div className="space-y-2">
            {data.items.map((reg) => (
              <RegistrationCard key={reg.id} registration={reg} />
            ))}
          </div>

          <Pagination
            page={page}
            totalPages={data.meta.total_pages}
            total={data.meta.total}
            perPage={data.meta.per_page}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}
