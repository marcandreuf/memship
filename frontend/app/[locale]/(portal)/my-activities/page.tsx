"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/lib/i18n/routing";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Pagination } from "@/components/entity/pagination";
import { toast } from "sonner";
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

  const imageUrl = activity?.image_url
    ? `/api/uploads${activity.image_url.replace("/uploads", "")}?t=${new Date(activity.updated_at).getTime()}`
    : null;

  return (
    <Link
      href={`/activities/${registration.activity_id}`}
      className="flex rounded-lg border overflow-hidden hover:bg-accent transition-colors"
    >
      <div className="flex-1 p-4">
        <h3 className="font-medium">
          {activity?.name || `Activity #${registration.activity_id}`}
        </h3>
        {activity && (
          <div className="mt-2 space-y-1 text-sm text-muted-foreground">
            <p>{formatDate(activity.starts_at)} — {formatDate(activity.ends_at)}</p>
            {activity.location && <p>{activity.location}</p>}
          </div>
        )}
        <p className="mt-1 text-xs text-muted-foreground">
          {t("activities.registration.registeredOn")}: {formatDate(registration.created_at)}
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <Badge variant={STATUS_VARIANTS[registration.status] || "outline"}>
            {t(`activities.registration.status.${registration.status}`)}
          </Badge>
          {canCancel && (
            <Button
              variant="outline"
              size="xs"
              onClick={async (e) => {
                e.preventDefault();
                if (confirm(t("activities.registration.confirmCancel"))) {
                  try {
                    await cancelMutation.mutateAsync({ id: registration.id });
                    toast.success(t("toast.success.updated"));
                  } catch { /* global handler shows error toast */ }
                }
              }}
              disabled={cancelMutation.isPending}
            >
              {t("common.cancel")}
            </Button>
          )}
        </div>
      </div>
      {imageUrl && (
        /* eslint-disable-next-line @next/next/no-img-element */
        <img
          src={imageUrl}
          alt={activity?.name || ""}
          className="w-28 object-cover shrink-0"
        />
      )}
    </Link>
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
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
