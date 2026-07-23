"use client";

import { useTranslations } from "next-intl";
import { FormSkeleton } from "@/components/ui/skeletons";
import { useSettings } from "@/features/settings/hooks/use-settings";
import {
  useCustomFields,
  useMyCustomFields,
  useUpdateMyCustomFields,
} from "../hooks/use-custom-fields";
import { CustomFieldsForm } from "./custom-fields-form";

/** The member's own custom fields — a tab on their profile page.
 *  Without this, a field set to member-writable would have nowhere to be
 *  written — members can't reach the member detail page. The tab trigger is
 *  gated on the feature flag by the profile page; this renders content only. */
export function MyCustomFields() {
  const t = useTranslations();
  const { data: settings } = useSettings();
  const enabled = Boolean(settings?.features?.custom_profile_fields);

  const { data: definitions = [], isLoading: loadingDefinitions } =
    useCustomFields(false, enabled);
  const { data: values = {}, isLoading: loadingValues } =
    useMyCustomFields(enabled);
  const updateMutation = useUpdateMyCustomFields();

  if (!enabled) return null;
  if (loadingDefinitions || loadingValues) return <FormSkeleton fields={2} />;
  // Every field hidden from this member — say so rather than a blank panel.
  if (!definitions.length)
    return (
      <p className="text-sm text-muted-foreground">
        {t("profileFields.noFieldsForMember")}
      </p>
    );

  return (
    <div className="max-w-2xl">
      <CustomFieldsForm
        definitions={definitions}
        values={values}
        onSave={(next) => updateMutation.mutateAsync(next)}
        isSaving={updateMutation.isPending}
      />
    </div>
  );
}
