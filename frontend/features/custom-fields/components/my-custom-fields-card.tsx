"use client";

import { useTranslations } from "next-intl";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FormSkeleton } from "@/components/ui/skeletons";
import { useSettings } from "@/features/settings/hooks/use-settings";
import {
  useCustomFields,
  useMyCustomFields,
  useUpdateMyCustomFields,
} from "../hooks/use-custom-fields";
import { CustomFieldsForm } from "./custom-fields-form";

/** The member's own custom fields, on their profile page.
 *  Without this, a field set to member-writable would have nowhere to be
 *  written — members can't reach the member detail page. */
export function MyCustomFieldsCard() {
  const t = useTranslations();
  const { data: settings } = useSettings();
  const enabled = Boolean(settings?.features?.custom_profile_fields);

  const { data: definitions = [], isLoading: loadingDefinitions } =
    useCustomFields(false, enabled);
  const { data: values = {}, isLoading: loadingValues } =
    useMyCustomFields(enabled);
  const updateMutation = useUpdateMyCustomFields();

  // Nothing to show when the feature is off, or when every field is hidden
  // from this member.
  if (!enabled) return null;
  if (!loadingDefinitions && !definitions.length) return null;

  return (
    <Card>
      <CardHeader className="py-3 px-4">
        <CardTitle className="text-base">{t("profileFields.tabLabel")}</CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-4 pt-0">
        {loadingDefinitions || loadingValues ? (
          <FormSkeleton fields={2} />
        ) : (
          <CustomFieldsForm
            definitions={definitions}
            values={values}
            onSave={(next) => updateMutation.mutateAsync(next)}
            isSaving={updateMutation.isPending}
          />
        )}
      </CardContent>
    </Card>
  );
}
