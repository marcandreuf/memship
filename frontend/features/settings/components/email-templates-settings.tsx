"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { FormSkeleton } from "@/components/ui/skeletons";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  useCommunicationsConfig,
  useUpdateCommunicationsConfig,
} from "../hooks/use-communications-config";
import { useSettings } from "../hooks/use-settings";
import type { CommunicationTemplateView } from "../services/communications-api";

// Templates whose feature can be switched off wholesale elsewhere in Settings.
// With the feature off the endpoint behind it 404s, so the row is inert — show
// it disabled rather than letting it read as a live choice.
const TEMPLATE_FEATURES: Record<string, string> = {
  announcement: "communications",
};

// The order groups are rendered in. A group the backend adds later still shows,
// appended after these.
const GROUP_ORDER = [
  "auth",
  "members",
  "activities",
  "bookings",
  "billing",
  "broadcasts",
];

function groupTemplates(templates: CommunicationTemplateView[]) {
  const groups = new Map<string, CommunicationTemplateView[]>();
  for (const template of templates) {
    const bucket = groups.get(template.group) ?? [];
    bucket.push(template);
    groups.set(template.group, bucket);
  }
  return [...groups.entries()].sort(
    ([a], [b]) =>
      (GROUP_ORDER.indexOf(a) + 1 || Number.MAX_SAFE_INTEGER) -
      (GROUP_ORDER.indexOf(b) + 1 || Number.MAX_SAFE_INTEGER)
  );
}

export function EmailTemplatesSettings() {
  const t = useTranslations();
  const { data, isLoading } = useCommunicationsConfig();
  const { data: settings } = useSettings();
  const updateMutation = useUpdateCommunicationsConfig();
  const [confirmDialog, confirmAction] = useConfirmDialog();

  // Local draft so a whole set of changes is saved in one request, matching the
  // other settings panels.
  const [draft, setDraft] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (data) {
      setDraft(
        Object.fromEntries(data.templates.map((tpl) => [tpl.key, tpl.enabled]))
      );
    }
  }, [data]);

  const grouped = useMemo(
    () => groupTemplates(data?.templates ?? []),
    [data]
  );

  const dirty = useMemo(() => {
    if (!data) return false;
    return data.templates.some((tpl) => draft[tpl.key] !== tpl.enabled);
  }, [data, draft]);

  if (isLoading) return <FormSkeleton fields={6} />;

  // Undefined settings means the fetch is still in flight — treat the feature
  // as on so a live row never flashes disabled.
  function disablingFeature(template: CommunicationTemplateView) {
    const feature = TEMPLATE_FEATURES[template.key];
    if (!feature || !settings) return null;
    return settings.features?.[feature] ? null : feature;
  }

  function applyToggle(template: CommunicationTemplateView, next: boolean) {
    // Switching an operational template off means a member stops hearing about
    // something they have no other signal for — confirm before staging it.
    if (!next && template.tier === "operational") {
      confirmAction({
        title: t("settings.emailTemplates.confirmDisableTitle", {
          name: t(`settings.emailTemplates.templates.${template.key}.name`),
        }),
        description: t(
          `settings.emailTemplates.templates.${template.key}.warning`
        ),
        confirmLabel: t("settings.emailTemplates.confirmDisable"),
        cancelLabel: t("common.cancel"),
        onConfirm: () => setDraft((d) => ({ ...d, [template.key]: false })),
      });
      return;
    }
    setDraft((d) => ({ ...d, [template.key]: next }));
  }

  async function onSave() {
    if (!data) return;
    // Send only what actually changed — the endpoint is sparse.
    const templates = Object.fromEntries(
      data.templates
        .filter((tpl) => draft[tpl.key] !== tpl.enabled)
        .map((tpl) => [tpl.key, draft[tpl.key]])
    );
    try {
      await updateMutation.mutateAsync({ templates });
      toast.success(t("toast.success.saved"));
    } catch {
      toast.error(t("toast.error.generic"));
    }
  }

  return (
    <div className="space-y-3 max-w-4xl">
      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-base">
            {t("settings.emailTemplates.title")}
          </CardTitle>
          <CardDescription className="text-xs">
            {t("settings.emailTemplates.description")}
          </CardDescription>
        </CardHeader>
        <CardContent className="px-4 pb-3 pt-0 space-y-4">
          {grouped.map(([group, templates]) => (
            <div key={group} className="space-y-2">
              <div>
                <h3 className="text-xs font-medium">
                  {t(`settings.emailTemplates.groups.${group}`)}
                </h3>
                <p className="text-xs text-muted-foreground">
                  {t(`settings.emailTemplates.groupDescriptions.${group}`)}
                </p>
              </div>
              {templates.map((template) => {
                const mandatory = template.tier === "mandatory";
                const featureOff = disablingFeature(template);
                return (
                  <div
                    key={template.key}
                    className="flex items-center justify-between gap-2 rounded-lg border p-2.5"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-medium">
                          {t(
                            `settings.emailTemplates.templates.${template.key}.name`
                          )}
                        </span>
                        {mandatory && (
                          <Badge variant="secondary" className="gap-1 text-[10px]">
                            <Lock className="h-3 w-3" />
                            {t("settings.emailTemplates.tiers.mandatory")}
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {featureOff
                          ? t(`settings.emailTemplates.featureOff.${featureOff}`)
                          : mandatory
                            ? t(
                                `settings.emailTemplates.templates.${template.key}.locked`
                              )
                            : t(
                                `settings.emailTemplates.templates.${template.key}.description`
                              )}
                      </p>
                    </div>
                    <Switch
                      checked={mandatory ? true : (draft[template.key] ?? true)}
                      disabled={mandatory || featureOff !== null}
                      onCheckedChange={(next) => applyToggle(template, next)}
                      aria-label={t(
                        `settings.emailTemplates.templates.${template.key}.name`
                      )}
                    />
                  </div>
                );
              })}
            </div>
          ))}
        </CardContent>
      </Card>

      <Button onClick={onSave} disabled={!dirty || updateMutation.isPending}>
        {updateMutation.isPending ? t("common.loading") : t("common.save")}
      </Button>

      {confirmDialog}
    </div>
  );
}
